"""
Gera um relatório HTML visual a partir do relatorio_varredura.csv
(o CSV gerado pelo varredura_palavras.py).

Como usar:
- Rode DEPOIS de já ter rodado o varredura_palavras.py (precisa existir o CSV).
- python gerar_relatorio_html.py
- Abre o arquivo "relatorio_visual.html" gerado, no navegador.
"""

import csv
import re
import html
from collections import defaultdict
from datetime import datetime

INPUT_CSV = "relatorio_varredura.csv"
OUTPUT_HTML = "relatorio_visual.html"


def destacar_palavra(contexto, palavra):
    """Envolve a palavra encontrada em um <mark> para destacar no HTML."""
    contexto_escapado = html.escape(contexto)
    padrao = re.compile(re.escape(html.escape(palavra)), re.IGNORECASE)
    return padrao.sub(lambda m: f'<mark>{m.group(0)}</mark>', contexto_escapado)


def main():
    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"Não encontrei o arquivo {INPUT_CSV}. Rode primeiro o varredura_palavras.py")
        return

    if not linhas:
        print("O CSV está vazio, nenhuma ocorrência para mostrar.")
        return

    # Agrupa por URL
    por_url = defaultdict(list)
    contagem_palavras = defaultdict(int)
    for linha in linhas:
        por_url[linha["url"]].append(linha)
        contagem_palavras[linha["palavra"]] += 1

    total_ocorrencias = len(linhas)
    total_paginas = len(por_url)
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")

    # Monta cards de resumo por palavra
    resumo_palavras_html = "".join(
        f'<div class="stat-card"><span class="stat-num">{qtd}</span><span class="stat-label">{html.escape(palavra)}</span></div>'
        for palavra, qtd in sorted(contagem_palavras.items(), key=lambda x: -x[1])
    )

    # Monta blocos por página
    blocos_html = ""
    for url, ocorrencias in sorted(por_url.items(), key=lambda x: -len(x[1])):
        itens = ""
        for oc in ocorrencias:
            trecho_destacado = destacar_palavra(oc["contexto"], oc["palavra"])
            itens += f"""
            <li class="ocorrencia">
                <span class="badge">{html.escape(oc['palavra'])}</span>
                <span class="trecho">{trecho_destacado}</span>
            </li>"""

        blocos_html += f"""
        <div class="pagina-card">
            <div class="pagina-header">
                <a href="{html.escape(url)}" target="_blank" class="pagina-url">{html.escape(url)}</a>
                <span class="pagina-count">{len(ocorrencias)} ocorrência(s)</span>
            </div>
            <ul class="ocorrencias-lista">{itens}
            </ul>
        </div>"""

    html_final = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<title>Relatório de Varredura — Palavras Restritas</title>
<style>
  :root {{
    --bg: #0f1115;
    --panel: #161923;
    --border: #262b38;
    --text: #e7e9ee;
    --muted: #9aa1b1;
    --accent: #ff8a5c;
    --accent-soft: rgba(255, 138, 92, 0.15);
    --mono: 'IBM Plex Mono', 'Courier New', monospace;
    --sans: 'IBM Plex Sans', 'Segoe UI', sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    padding: 48px 24px 80px;
  }}
  .container {{ max-width: 920px; margin: 0 auto; }}
  header {{ margin-bottom: 40px; }}
  .eyebrow {{
    font-family: var(--mono);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 12px;
    color: var(--accent);
    margin-bottom: 12px;
  }}
  h1 {{
    font-size: 32px;
    margin: 0 0 8px;
    line-height: 1.2;
    letter-spacing: -0.01em;
  }}
  .subtitulo {{ color: var(--muted); font-size: 14px; }}

  .stats-row {{
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin: 32px 0 40px;
  }}
  .stat-card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    min-width: 100px;
  }}
  .stat-num {{
    font-family: var(--mono);
    font-size: 24px;
    font-weight: 600;
    color: var(--accent);
  }}
  .stat-label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }}

  .totais {{
    font-family: var(--mono);
    font-size: 13px;
    color: var(--muted);
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 12px 0;
    margin-bottom: 32px;
  }}
  .totais b {{ color: var(--text); }}

  .pagina-card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 16px;
    overflow: hidden;
  }}
  .pagina-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border);
    background: rgba(255,255,255,0.02);
    flex-wrap: wrap;
  }}
  .pagina-url {{
    font-family: var(--mono);
    font-size: 13px;
    color: var(--text);
    text-decoration: none;
    word-break: break-all;
  }}
  .pagina-url:hover {{ color: var(--accent); text-decoration: underline; }}
  .pagina-count {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--accent);
    background: var(--accent-soft);
    padding: 3px 10px;
    border-radius: 999px;
    white-space: nowrap;
  }}
  .ocorrencias-lista {{ list-style: none; margin: 0; padding: 0; }}
  .ocorrencia {{
    display: flex;
    gap: 12px;
    align-items: baseline;
    padding: 12px 18px;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }}
  .ocorrencia:last-child {{ border-bottom: none; }}
  .badge {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--bg);
    background: var(--accent);
    padding: 2px 8px;
    border-radius: 4px;
    flex-shrink: 0;
    height: fit-content;
    font-weight: 600;
  }}
  .trecho {{ color: var(--muted); line-height: 1.5; }}
  .trecho mark {{
    background: var(--accent-soft);
    color: var(--accent);
    padding: 0 3px;
    border-radius: 3px;
    font-weight: 600;
  }}
  footer {{
    margin-top: 40px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    text-align: center;
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="eyebrow">Varredura de conformidade — Meta Ads</div>
    <h1>Palavras restritas encontradas no site</h1>
    <div class="subtitulo">Gerado em {data_geracao}</div>
  </header>

  <div class="stats-row">
    {resumo_palavras_html}
  </div>

  <div class="totais">
    <b>{total_ocorrencias}</b> ocorrências encontradas em <b>{total_paginas}</b> páginas.
  </div>

  {blocos_html}

  <footer>Relatório gerado automaticamente a partir de {INPUT_CSV}</footer>
</div>
</body>
</html>"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_final)

    print(f"Relatório visual gerado: {OUTPUT_HTML}")
    print(f"Abra esse arquivo no navegador para visualizar.")


if __name__ == "__main__":
    main()
