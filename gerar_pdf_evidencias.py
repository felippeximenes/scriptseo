"""
Junta os prints gerados pelo capturar_prints.py + as informações do
relatorio_varredura.csv em um único PDF, com o link de cada página
clicável e o trecho da palavra encontrada.

PRÉ-REQUISITO (rodar uma vez no terminal):
    pip install reportlab

Como usar:
- Rode DEPOIS do capturar_prints.py (precisa existir a pasta prints_evidencia/
  e o arquivo relatorio_varredura.csv, ambos gerados pelos scripts anteriores).
- python gerar_pdf_evidencias.py
- Gera o arquivo "evidencias_varredura.pdf" com um bloco por página:
  link da URL (clicável), o print, e a lista de palavras/trechos encontrados.
"""

import csv
import re
import html
from pathlib import Path
from collections import defaultdict
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, KeepTogether
)
from reportlab.lib.utils import ImageReader

INPUT_CSV = "relatorio_varredura.csv"
PASTA_PRINTS = "prints_evidencia"
OUTPUT_PDF = "evidencias_varredura.pdf"

COR_DESTAQUE = "#e8590c"
COR_LINK = "#1a5fb4"
COR_TEXTO = "#2b2b2b"
COR_MUTED = "#6c757d"
COR_LINHA = "#dee2e6"
COR_FUNDO_HEADER = "#f1f3f5"


def nome_arquivo_seguro(url):
    """Mesma lógica usada no capturar_prints.py, para achar o print de cada URL."""
    nome = re.sub(r"^https?://", "", url)
    nome = re.sub(r"[^a-zA-Z0-9]+", "_", nome).strip("_")
    return nome[:150] + ".png"


def destacar_palavra_pdf(contexto, palavra):
    """Escapa o texto e envolve a palavra encontrada com <font color=...> para destacar no PDF."""
    contexto_escapado = html.escape(contexto)
    palavra_escapada = html.escape(palavra)
    padrao = re.compile(re.escape(palavra_escapada), re.IGNORECASE)
    return padrao.sub(
        lambda m: f'<font color="{COR_DESTAQUE}"><b>{m.group(0)}</b></font>',
        contexto_escapado
    )


def montar_estilos():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TituloCapa", fontSize=24, leading=29, spaceAfter=8,
        fontName="Helvetica-Bold", textColor=colors.HexColor(COR_TEXTO)
    ))
    styles.add(ParagraphStyle(
        name="SubtituloCapa", fontSize=11, textColor=colors.HexColor(COR_MUTED),
        spaceAfter=16, fontName="Helvetica"
    ))
    styles.add(ParagraphStyle(
        name="CapaCorpo", fontSize=10.5, leading=15,
        textColor=colors.HexColor(COR_TEXTO), spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="LinkPagina", fontSize=11.5, fontName="Helvetica-Bold",
        textColor=colors.HexColor(COR_LINK), spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name="ContagemPagina", fontSize=9, textColor=colors.HexColor(COR_MUTED),
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name="CelulaPalavra", fontSize=9, fontName="Helvetica-Bold",
        textColor=colors.HexColor(COR_DESTAQUE), leading=12
    ))
    styles.add(ParagraphStyle(
        name="CelulaTrecho", fontSize=9, leading=13,
        textColor=colors.HexColor(COR_TEXTO)
    ))
    styles.add(ParagraphStyle(
        name="CabecalhoTabela", fontSize=9, fontName="Helvetica-Bold",
        textColor=colors.HexColor(COR_TEXTO)
    ))
    styles.add(ParagraphStyle(
        name="AvisoSemPrint", fontSize=9.5, fontName="Helvetica-Oblique",
        textColor=colors.HexColor(COR_MUTED), spaceAfter=6
    ))
    return styles


def calcular_dimensoes_imagem(caminho_imagem, largura_max, altura_max):
    """Calcula largura/altura da imagem mantendo proporção, respeitando os limites."""
    img_reader = ImageReader(str(caminho_imagem))
    largura_original, altura_original = img_reader.getSize()
    proporcao = largura_original / altura_original

    largura = largura_max
    altura = largura / proporcao

    if altura > altura_max:
        altura = altura_max
        largura = altura * proporcao

    return largura, altura


def main():
    try:
        with open(INPUT_CSV, newline="", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"Não encontrei {INPUT_CSV}. Rode primeiro o varredura_palavras.py")
        return

    if not linhas:
        print("CSV vazio, nada para colocar no PDF.")
        return

    por_url = defaultdict(list)
    por_palavra = defaultdict(lambda: {"ocorrencias": 0, "urls": set()})
    for linha in linhas:
        por_url[linha["url"]].append(linha)
        por_palavra[linha["palavra"]]["ocorrencias"] += 1
        por_palavra[linha["palavra"]]["urls"].add(linha["url"])

    pasta_prints = Path(PASTA_PRINTS)
    styles = montar_estilos()
    story = []

    LARGURA_PAGINA = A4[0] - 4 * cm  # descontando as margens esquerda+direita (2cm cada)

    # ---------- Capa ----------
    data_geracao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    total_ocorrencias = len(linhas)
    total_paginas = len(por_url)

    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("Evidências — Varredura de Palavras Restritas", styles["TituloCapa"]))
    story.append(Paragraph(
        f"Gerado em {data_geracao} &nbsp;•&nbsp; {total_ocorrencias} ocorrências "
        f"encontradas em {total_paginas} páginas",
        styles["SubtituloCapa"]
    ))
    story.append(Paragraph(
        "Este documento reúne os prints das páginas do site onde foram encontradas "
        "palavras relacionadas a criptomoedas/web3, com o link direto de cada página "
        "e o trecho de texto correspondente, para uso na revisão da conta de anúncios.",
        styles["CapaCorpo"]
    ))

    # Resumo por palavra-chave — visão geral bem visível de tudo que foi encontrado,
    # antes de entrar no detalhe página a página.
    story.append(Spacer(1, 12))
    story.append(Paragraph("Resumo por palavra-chave", styles["LinkPagina"]))
    story.append(Spacer(1, 6))
    dados_resumo = [[
        Paragraph("Palavra", styles["CabecalhoTabela"]),
        Paragraph("Ocorrências", styles["CabecalhoTabela"]),
        Paragraph("Páginas", styles["CabecalhoTabela"]),
    ]]
    for palavra, dados in sorted(por_palavra.items(), key=lambda x: -x[1]["ocorrencias"]):
        dados_resumo.append([
            Paragraph(html.escape(palavra), styles["CelulaPalavra"]),
            Paragraph(str(dados["ocorrencias"]), styles["CelulaTrecho"]),
            Paragraph(str(len(dados["urls"])), styles["CelulaTrecho"]),
        ])
    tabela_resumo = Table(
        dados_resumo,
        colWidths=[LARGURA_PAGINA * 0.4, LARGURA_PAGINA * 0.3, LARGURA_PAGINA * 0.3],
    )
    tabela_resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COR_FUNDO_HEADER)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COR_LINHA)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tabela_resumo)
    story.append(PageBreak())

    # ---------- Um bloco por página ----------
    paginas_sem_print = []

    for url, ocorrencias in sorted(por_url.items(), key=lambda x: -len(x[1])):
        cabecalho = []
        cabecalho.append(Paragraph(f'<link href="{url}" color="{COR_LINK}">{html.escape(url)}</link>', styles["LinkPagina"]))
        plural = "ocorrência" if len(ocorrencias) == 1 else "ocorrências"
        cabecalho.append(Paragraph(f"{len(ocorrencias)} {plural} encontrada(s) nesta página", styles["ContagemPagina"]))

        # Imagem (se existir) — largura de segurança um pouco menor que a área útil da página,
        # e altura máxima calculada para nunca ultrapassar o espaço de uma página A4.
        caminho_imagem = pasta_prints / nome_arquivo_seguro(url)
        elementos_imagem = []
        if caminho_imagem.exists():
            largura_max = LARGURA_PAGINA - 0.4 * cm
            altura_max = 15 * cm  # deixa espaço garantido pro cabeçalho + tabela abaixo
            largura, altura = calcular_dimensoes_imagem(caminho_imagem, largura_max, altura_max)
            elementos_imagem.append(Spacer(1, 6))
            elementos_imagem.append(Image(str(caminho_imagem), width=largura, height=altura))
            elementos_imagem.append(Spacer(1, 10))
        else:
            paginas_sem_print.append(url)
            elementos_imagem.append(Paragraph(
                "Print não encontrado para esta página (rode capturar_prints.py para gerá-lo).",
                styles["AvisoSemPrint"]
            ))

        # Mantém cabeçalho + imagem juntos na mesma página (evita cortar a imagem ao meio)
        story.append(KeepTogether(cabecalho + elementos_imagem))

        # Tabela com palavra + trecho — usando Paragraph nas células para quebrar linha
        # corretamente em vez de estourar para fora da página.
        col_palavra = 2.6 * cm
        col_trecho = LARGURA_PAGINA - col_palavra

        dados_tabela = [[
            Paragraph("Palavra", styles["CabecalhoTabela"]),
            Paragraph("Trecho", styles["CabecalhoTabela"]),
        ]]
        for oc in ocorrencias:
            trecho_destacado = destacar_palavra_pdf(oc["contexto"], oc["palavra"])
            dados_tabela.append([
                Paragraph(html.escape(oc["palavra"]), styles["CelulaPalavra"]),
                Paragraph(trecho_destacado, styles["CelulaTrecho"]),
            ])

        tabela = Table(dados_tabela, colWidths=[col_palavra, col_trecho], repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COR_FUNDO_HEADER)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COR_LINHA)),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(tabela)
        story.append(Spacer(1, 24))
        story.append(PageBreak())

    doc = SimpleDocTemplate(
        OUTPUT_PDF, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm
    )

    def numerar_paginas(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor(COR_MUTED))
        canvas_obj.drawRightString(
            A4[0] - 2 * cm, 1.2 * cm, f"Página {doc_obj.page}"
        )
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=numerar_paginas, onLaterPages=numerar_paginas)

    print(f"PDF gerado: {OUTPUT_PDF}")
    if paginas_sem_print:
        print(f"\nAtenção: {len(paginas_sem_print)} página(s) sem print encontrado:")
        for url in paginas_sem_print:
            print(f"  - {url}")
        print("Rode capturar_prints.py novamente para gerar os prints faltantes.")


if __name__ == "__main__":
    main()
