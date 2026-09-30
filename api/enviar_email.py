"""POST /api/enviar_email: chamado pelos Database Webhooks do Supabase.

Toda tentativa de envio grava uma linha em emails_enviados, com sucesso ou falha.
"""

import hmac
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _lib import config, emails, resend, supabase  # noqa: E402
from _lib.resposta import Handler  # noqa: E402

VALIDADE_LINK_PDF = 7 * 24 * 3600


def _contexto(tipo, evento):
    novo = evento["record"]
    paroquia = supabase.selecionar_um("paroquias", {"id": "eq." + novo["paroquia_id"], "select": "nome"})
    ctx = {"paroquia": paroquia["nome"] if paroquia else ""}

    if evento["table"] == "pagamentos":
        ctx["valor"] = novo["valor"]
    else:
        ctx["sacramento"] = novo["tipo"]
        ctx["motivo"] = novo.get("motivo_rejeicao")
        if tipo == "certidao_aprovada":
            ctx["link_pdf"] = supabase.url_assinada(
                config.BUCKET_CERTIDOES,
                "{}/{}.pdf".format(novo["solicitante_id"], novo["id"]),
                VALIDADE_LINK_PDF,
            )
    return ctx


def processar(evento):
    tipo = emails.classificar(evento)
    if not tipo:
        return {"ignorado": True}

    destinatario = ""
    status_envio = "falhou"
    try:
        destinatario, nome = supabase.email_do_perfil(emails.destinatario_perfil_id(evento))
        destinatario = destinatario or ""
        if destinatario:
            ctx = _contexto(tipo, evento)
            ctx["nome"] = nome
            assunto, html = emails.montar(tipo, ctx)
            resend.enviar(destinatario, assunto, html)
            status_envio = "enviado"
    except Exception:  # noqa: BLE001 - qualquer falha vira registro "falhou"
        status_envio = "falhou"

    supabase.inserir("emails_enviados", {
        "destinatario_email": destinatario,
        "tipo": tipo,
        "referencia_tabela": evento["table"],
        "referencia_id": evento["record"]["id"],
        "status_envio": status_envio,
    })
    return {"tipo": tipo, "status_envio": status_envio}


class handler(Handler):
    def do_POST(self):
        segredo = self.headers.get("X-Webhook-Secret") or ""
        if not hmac.compare_digest(segredo, config.obrigatoria("EMAIL_WEBHOOK_SECRET")):
            return self.responder(401, {"erro": "não autorizado"})
        evento = self.ler_json()
        if not evento or not evento.get("record"):
            return self.responder(400, {"erro": "payload inválido"})
        self.responder(200, processar(evento))
