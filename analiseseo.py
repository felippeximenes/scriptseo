"""
Script de varredura de palavras-chave em um site.

O que ele faz:
1. Tenta ler o sitemap.xml do site (ou sitemaps aninhados) para pegar a lista de URLs.
   Se não achar sitemap, faz um crawler simples a partir da home, seguindo links internos.
2. Para cada página, baixa o HTML, extrai o texto visível e verifica se alguma das
   palavras-chave (ex.: "cripto", "web3") aparece.
3. Gera um relatório (arquivo CSV) com: URL, palavra encontrada, e um trecho de contexto
   (para facilitar localizar e remover o termo depois).

Como usar:
- Ajuste BASE_URL para o domínio do site.
- Ajuste KEYWORDS com os termos que quer buscar.
- Rode: python varredura_palavras.py
- O resultado aparece no terminal e também é salvo em "relatorio_varredura.csv"
"""

import re
import csv
import time
from urllib.parse import urljoin, urlparse
from collections import deque

import requests
from bs4 import BeautifulSoup

# ======================= CONFIGURAÇÕES =======================
BASE_URL = "https://liberpay.com"   # <-- TROCAR pelo domínio real do site
KEYWORDS = ["cripto", "crypto", "web3", "bitcoin", "blockchain", "stablecoins", "criptomoedas"]  # <-- ajustar lista
MAX_PAGES = 200          # limite de segurança para não rodar infinitamente
TIMEOUT = 10             # segundos de timeout por requisição
DELAY_BETWEEN_REQUESTS = 0.5  # segundos entre requisições, para não sobrecarregar o servidor
OUTPUT_CSV = "relatorio_varredura.csv"
# ===============================================================


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VarreduraKeywordsBot/1.0)"
}


def tentar_sitemap(base_url):
    """Tenta encontrar URLs a partir do sitemap.xml (incluindo sitemaps aninhados)."""
    urls = set()
    candidatos = [urljoin(base_url, "/sitemap.xml"), urljoin(base_url, "/sitemap_index.xml")]

    fila = deque(candidatos)
    visitados = set()

    while fila:
        sitemap_url = fila.popleft()
        if sitemap_url in visitados:
            continue
        visitados.add(sitemap_url)

        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
        except requests.RequestException:
            continue

        try:
            soup = BeautifulSoup(resp.content, "xml")
        except Exception:
            soup = BeautifulSoup(resp.content, "html.parser")

        # Sitemap index (aponta para outros sitemaps)
        sitemap_tags = soup.find_all("sitemap")
        if sitemap_tags:
            for tag in sitemap_tags:
                loc = tag.find("loc")
                if loc and loc.text:
                    fila.append(loc.text.strip())
            continue

        # Sitemap normal (lista de páginas)
        url_tags = soup.find_all("url")
        for tag in url_tags:
            loc = tag.find("loc")
            if loc and loc.text:
                urls.add(loc.text.strip())

    return urls


def crawler_simples(base_url, max_pages):
    """Fallback: crawler simples seguindo links internos a partir da home."""
    dominio = urlparse(base_url).netloc
    visitados = set()
    fila = deque([base_url])
    encontrados = set()

    while fila and len(visitados) < max_pages:
        url = fila.popleft()
        if url in visitados:
            continue
        visitados.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
        except requests.RequestException:
            continue

        encontrados.add(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.find_all("a", href=True):
            href = urljoin(url, link["href"])
            href_parsed = urlparse(href)
            # Só segue links do mesmo domínio, ignora âncoras e arquivos não-HTML óbvios
            if href_parsed.netloc == dominio and href.startswith("http"):
                href_limpa = href.split("#")[0]
                if href_limpa not in visitados:
                    fila.append(href_limpa)

        time.sleep(DELAY_BETWEEN_REQUESTS)

    return encontrados


def extrair_contexto(texto, palavra, janela=60):
    """Retorna um trecho de texto ao redor da palavra encontrada, para dar contexto."""
    idx = texto.lower().find(palavra.lower())
    if idx == -1:
        return ""
    inicio = max(0, idx - janela)
    fim = min(len(texto), idx + len(palavra) + janela)
    trecho = texto[inicio:fim].replace("\n", " ").strip()
    return f"...{trecho}..."


def verificar_pagina(url, keywords):
    """Baixa a página e verifica quais keywords aparecem no texto visível."""
    resultados = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return resultados
    except requests.RequestException as e:
        print(f"  [erro] Não consegui acessar {url}: {e}")
        return resultados

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove scripts e estilos para não pegar falso-positivo em código
    for tag in soup(["script", "style"]):
        tag.decompose()

    texto = soup.get_text(separator=" ")

    for palavra in keywords:
        # \b garante que é a palavra "inteira" (evita pegar dentro de outra palavra qualquer)
        padrao = re.compile(r"\b" + re.escape(palavra) + r"\b", re.IGNORECASE)
        if padrao.search(texto):
            contexto = extrair_contexto(texto, palavra)
            resultados.append({"url": url, "palavra": palavra, "contexto": contexto})

    return resultados


def main():
    print(f"Iniciando varredura em: {BASE_URL}")
    print(f"Palavras-chave: {', '.join(KEYWORDS)}\n")

    print("Procurando sitemap.xml...")
    urls = tentar_sitemap(BASE_URL)

    if urls:
        print(f"Sitemap encontrado! {len(urls)} URLs listadas.")
        urls = list(urls)[:MAX_PAGES]
    else:
        print("Sitemap não encontrado (ou vazio). Fazendo crawler simples a partir da home...")
        urls = list(crawler_simples(BASE_URL, MAX_PAGES))
        print(f"Crawler encontrou {len(urls)} páginas.")

    if not urls:
        print("Nenhuma URL encontrada para verificar. Verifique o BASE_URL.")
        return

    todos_resultados = []
    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] Verificando: {url}")
        resultados = verificar_pagina(url, KEYWORDS)
        if resultados:
            for r in resultados:
                print(f"    >> encontrado '{r['palavra']}'")
            todos_resultados.extend(resultados)
        time.sleep(DELAY_BETWEEN_REQUESTS)

    # Salva relatório em CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "palavra", "contexto"])
        writer.writeheader()
        writer.writerows(todos_resultados)

    print(f"\nVarredura concluída. {len(todos_resultados)} ocorrências encontradas.")
    print(f"Relatório salvo em: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()