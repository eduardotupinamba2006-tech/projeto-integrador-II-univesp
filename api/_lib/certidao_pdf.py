"""Geração do PDF da certidão, sempre a partir do registro sacramental oficial."""

import io
from datetime import date, datetime

import segno
from fpdf import FPDF

TITULOS = {
    "batismo": "Certidão de Batismo",
    "primeira_comunhao": "Certidão de Primeira Comunhão",
    "crisma": "Certidão de Crisma",
    "casamento": "Certidão de Casamento",
    "ordenacao": "Certidão de Ordenação",
}

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def data_por_extenso(valor):
    if isinstance(valor, str):
        valor = date.fromisoformat(valor[:10])
    return "{} de {} de {}".format(valor.day, MESES[valor.month - 1], valor.year)


def gerar_pdf(registro, paroquia, diocese, url_validacao, emitida_em=None):
    """registro, paroquia e diocese são linhas das tabelas oficiais (dicts)."""
    emitida_em = emitida_em or datetime.now()

    pdf = FPDF(format="A4")
    pdf.set_title(TITULOS[registro["tipo"]])
    pdf.set_author(paroquia["nome"])
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, diocese["nome"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, paroquia["nome"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, paroquia["endereco"], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(12)

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, TITULOS[registro["tipo"]], align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        0, 7,
        "Certificamos que, conforme consta no livro de registros desta paróquia, "
        "{} recebeu o sacramento em {}.".format(registro["nome_pessoa"], data_por_extenso(registro["data_sacramento"])),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(6)

    campos = [
        ("Livro", registro.get("livro")),
        ("Folha", registro.get("folha")),
        ("Número", registro.get("numero")),
        ("Celebrante", registro.get("celebrante")),
        ("Testemunhas" if registro["tipo"] == "casamento" else "Padrinhos", registro.get("padrinhos")),
    ]
    for rotulo, valor in campos:
        if valor:
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(35, 7, rotulo + ":")
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(0, 7, str(valor), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Emitida em {}.".format(data_por_extenso(emitida_em.date())), new_x="LMARGIN", new_y="NEXT")

    qr = io.BytesIO()
    segno.make(url_validacao, error="m").save(qr, kind="png", scale=6, border=2)
    qr.seek(0)
    y = pdf.get_y() + 10
    pdf.image(qr, x=20, y=y, w=35, h=35)
    pdf.set_xy(60, y + 8)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(
        0, 5,
        "Verifique a autenticidade desta certidão lendo o QR Code ou acessando:\n" + url_validacao,
        new_x="LMARGIN", new_y="NEXT",
    )

    return bytes(pdf.output())
