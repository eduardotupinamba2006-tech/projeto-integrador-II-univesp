"""Envio de email pela API do Resend."""

from . import config
from .http import requisitar


def enviar(para, assunto, html):
    return requisitar(
        "POST",
        "https://api.resend.com/emails",
        headers={"Authorization": "Bearer " + config.obrigatoria("RESEND_API_KEY")},
        json_corpo={
            "from": config.obrigatoria("EMAIL_REMETENTE"),
            "to": [para],
            "subject": assunto,
            "html": html,
        },
    )
