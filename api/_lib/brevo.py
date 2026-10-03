"""Envio de email pela API transacional do Brevo."""

import re

from . import config
from .http import requisitar


def remetente():
    """Lê EMAIL_REMETENTE ("Nome <email>" ou só o email), que precisa estar verificado no Brevo."""
    bruto = config.obrigatoria("EMAIL_REMETENTE").strip()
    formato = re.fullmatch(r"\s*(.*?)\s*<\s*([^<>\s]+)\s*>\s*", bruto)
    if formato:
        nome, email = formato.groups()
        return {"name": nome.strip('"'), "email": email} if nome else {"email": email}
    return {"email": bruto}


def enviar(para, assunto, html):
    return requisitar(
        "POST",
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": config.obrigatoria("BREVO_API_KEY"),
            "Accept": "application/json",
            # O firewall do Brevo recusa o User-Agent padrão do urllib (erro 1010).
            "User-Agent": "certidoes-dizimo/1.0",
        },
        json_corpo={
            "sender": remetente(),
            "to": [{"email": para}],
            "subject": assunto,
            "htmlContent": html,
        },
    )
