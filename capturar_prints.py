"""
Abre cada página que teve ocorrência (a partir do relatorio_varredura.csv),
destaca visualmente a palavra encontrada (fundo amarelo) e salva um print
(screenshot) da página real, com a palavra já grifada.

PRÉ-REQUISITO (rodar uma vez no terminal):
    pip install playwright
    playwright install chromium

Como usar:
- Rode DEPOIS do varredura_palavras.py (precisa existir o relatorio_varredura.csv).
- python capturar_prints.py
- Os prints são salvos na pasta "prints_evidencia/", um arquivo por página,
  já com a(s) palavra(s) destacada(s) em amarelo.
"""

import csv
import io
import re
from pathlib import Path
from collections import defaultdict

from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw

INPUT_CSV = "relatorio_varredura.csv"
PASTA_SAIDA = "prints_evidencia"

# Em vez de tirar um print da página inteira (que em páginas com muitas seções
# fica espremido e ilegível quando redimensionado pro PDF), recorta só as
# seções onde as palavras aparecem, com uma margem de contexto acima/abaixo.
# Se a página tiver mais de uma ocorrência em pontos diferentes, cada seção
# vira um recorte separado e todos são empilhados num único print, na ordem
# em que aparecem na página.
MARGEM_CONTEXTO_RECORTE = 260  # pixels de contexto acima/abaixo de cada palavra
SEPARADOR_ALTURA = 14  # pixels da faixa cinza entre recortes de seções não-contíguas
COR_SEPARADOR = (222, 226, 230)


def nome_arquivo_seguro(url):
    """Transforma a URL num nome de arquivo válido."""
    nome = re.sub(r"^https?://", "", url)
    nome = re.sub(r"[^a-zA-Z0-9]+", "_", nome).strip("_")
    return nome[:150] + ".png"


def agrupar_marcas(pagina, margem, altura_pagina):
    """Agrupa os índices dos <mark> da página por proximidade vertical: marcas
    cuja faixa de contexto (posição ± margem) se sobrepõe caem no mesmo grupo,
    pra virarem um recorte só em vez de dois quase idênticos."""
    marcas = pagina.locator("mark")
    itens = [(i, c) for i, c in ((i, marcas.nth(i).bounding_box()) for i in range(marcas.count())) if c]
    itens.sort(key=lambda t: t[1]["y"])

    grupos = []
    grupo_atual = []
    limite_atual = None
    for i, c in itens:
        y0 = max(0, c["y"] - margem)
        y1 = min(altura_pagina, c["y"] + c["height"] + margem)
        if limite_atual is None or y0 <= limite_atual:
            grupo_atual.append(i)
            limite_atual = max(limite_atual or y1, y1)
        else:
            grupos.append(grupo_atual)
            grupo_atual = [i]
            limite_atual = y1
    if grupo_atual:
        grupos.append(grupo_atual)
    return grupos


def calcular_regiao_atual(pagina, indices, margem):
    """Rola a página até o grupo ficar visível e remede a posição das marcas
    já relativa a essa rolagem, bem em cima da hora do print. Necessário por
    dois motivos: (1) o clip do Playwright só é válido dentro do viewport
    atualmente renderizado, não do documento inteiro; e (2) em páginas com
    texto animado (ex.: título com efeito de digitação) a posição pode mudar
    entre a medição e o screenshot, então remedir na hora evita recorte errado."""
    marcas = pagina.locator("mark")
    marcas.nth(indices[0]).scroll_into_view_if_needed()

    caixas = [c for c in (marcas.nth(i).bounding_box() for i in indices) if c]
    if not caixas:
        return None

    viewport_altura = pagina.viewport_size["height"]
    y0 = max(0, min(c["y"] for c in caixas) - margem)
    y1 = min(viewport_altura, max(c["y"] + c["height"] for c in caixas) + margem)
    if y1 <= y0:
        return None
    return y0, y1 - y0  # y_topo (relativo ao viewport atual), altura do recorte


def unir_recortes_verticalmente(imagens):
    """Empilha os recortes de seção num único print, com uma faixa cinza fina
    separando trechos que não são contíguos na página original."""
    largura = max(img.width for img in imagens)
    altura_total = sum(img.height for img in imagens) + SEPARADOR_ALTURA * (len(imagens) - 1)
    composta = Image.new("RGB", (largura, altura_total), "white")
    draw = ImageDraw.Draw(composta)

    y = 0
    for i, img in enumerate(imagens):
        composta.paste(img, (0, y))
        y += img.height
        if i < len(imagens) - 1:
            draw.rectangle([0, y, largura, y + SEPARADOR_ALTURA], fill=COR_SEPARADOR)
            y += SEPARADOR_ALTURA
    return composta


def main():
    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"Não encontrei {INPUT_CSV}. Rode primeiro o varredura_palavras.py")
        return

    if not linhas:
        print("CSV vazio, nada para capturar.")
        return

    # Agrupa as palavras por URL (uma página pode ter mais de uma palavra encontrada)
    palavras_por_url = defaultdict(set)
    for linha in linhas:
        palavras_por_url[linha["url"]].add(linha["palavra"])

    Path(PASTA_SAIDA).mkdir(exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 1366, "height": 900})

        for url, palavras in palavras_por_url.items():
            print(f"Abrindo: {url}  (palavras: {', '.join(palavras)})")

            # Tenta esperar a rede ficar quieta (páginas mais completas);
            # se demorar demais (algumas páginas nunca "sossegam" por causa de
            # scripts de terceiros, tipo chat/analytics), cai para uma espera
            # mais simples em vez de desistir da página inteira.
            carregou = False
            try:
                pagina.goto(url, timeout=45000, wait_until="networkidle")
                carregou = True
            except Exception:
                try:
                    pagina.goto(url, timeout=45000, wait_until="load")
                    pagina.wait_for_timeout(2000)
                    carregou = True
                except Exception as e:
                    print(f"  [erro] não consegui abrir {url}: {e}")
                    continue

            if not carregou:
                continue

            # Injeta um script que percorre o texto da página e envolve
            # cada palavra encontrada num <mark> (fundo amarelo), sem
            # alterar links nem quebrar o layout.
            # Antes de mexer em cada trecho de texto, verifica se o elemento
            # usa efeitos especiais de estilo (ex.: texto com gradiente via
            # "background-clip: text"), e se usar, pula o destaque ali —
            # senão o texto some visualmente (vira uma caixa vazia).
            palavras_js = list(palavras)
            pagina.evaluate(
                """(palavras) => {
                    const regexes = palavras.map(p => new RegExp('\\\\b(' + p + ')\\\\b', 'gi'));

                    function usaEstiloEspecial(elemento) {
                        if (!elemento || elemento.nodeType !== 1) return false;
                        const estilo = window.getComputedStyle(elemento);
                        const clip = estilo.webkitBackgroundClip || estilo.backgroundClip || '';
                        return clip.includes('text');
                    }

                    function destacarTexto(node) {
                        if (node.nodeType === 3) { // nó de texto
                            let texto = node.nodeValue;
                            let algumaOcorrencia = false;
                            for (const r of regexes) {
                                if (r.test(texto)) { algumaOcorrencia = true; break; }
                            }
                            if (!algumaOcorrencia) return;

                            // Pula elementos com texto estilizado (gradiente, clip, etc.)
                            // para não quebrar o efeito visual do título.
                            if (usaEstiloEspecial(node.parentElement)) return;

                            const span = document.createElement('span');
                            let html = texto;
                            for (const r of regexes) {
                                html = html.replace(r, '<mark style="background:#ffe066;color:#111;padding:0 2px;border-radius:2px;">$1</mark>');
                            }
                            span.innerHTML = html;
                            node.replaceWith(span);
                        } else if (node.nodeType === 1 && node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE') {
                            // copia os filhos para uma lista fixa, pois vamos alterar a árvore
                            Array.from(node.childNodes).forEach(destacarTexto);
                        }
                    }

                    destacarTexto(document.body);
                }""",
                palavras_js,
            )

            caminho_print = Path(PASTA_SAIDA) / nome_arquivo_seguro(url)
            try:
                altura_pagina = pagina.evaluate("document.body.scrollHeight")
                largura_viewport = pagina.viewport_size["width"]
                grupos = agrupar_marcas(pagina, MARGEM_CONTEXTO_RECORTE, altura_pagina)

                recortes = []
                for indices in grupos:
                    regiao = calcular_regiao_atual(pagina, indices, MARGEM_CONTEXTO_RECORTE)
                    if not regiao:
                        continue
                    y_topo, altura_recorte = regiao
                    try:
                        buffer = pagina.screenshot(
                            clip={"x": 0, "y": y_topo, "width": largura_viewport, "height": altura_recorte},
                            timeout=30000,
                        )
                        recortes.append(Image.open(io.BytesIO(buffer)))
                    except Exception:
                        # Página com conteúdo animado (ex.: título com efeito de digitação)
                        # mudou de posição entre a medição e o print — desiste dos recortes
                        # e cai pro print de página inteira abaixo, que sempre funciona.
                        recortes = []
                        break

                if recortes:
                    imagem_final = recortes[0] if len(recortes) == 1 else unir_recortes_verticalmente(recortes)
                    imagem_final.save(caminho_print)
                    print(f"  print ({len(recortes)} seção(ões) recortada(s)) salvo em: {caminho_print}")
                else:
                    pagina.screenshot(path=str(caminho_print), full_page=True, timeout=30000)
                    print(f"  print (página inteira, fallback) salvo em: {caminho_print}")
            except Exception as e:
                print(f"  [erro] não consegui tirar o print de {url}: {e}")

        navegador.close()

    print(f"\nConcluído. Prints salvos na pasta '{PASTA_SAIDA}/'.")


if __name__ == "__main__":
    main()