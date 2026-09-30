"""API Pix do Mercado Pago (sandbox enquanto MP_ACCESS_TOKEN for de teste)."""

import hashlib
import hmac

from . import config
from .http import requisitar

API = "https://api.mercadopago.com"


def _headers(extra=None):
    h = {"Authorization": "Bearer " + config.obrigatoria("MP_ACCESS_TOKEN")}
    h.update(extra or {})
    return h


def criar_pix(pagamento_id, valor, descricao, email_pagador, url_notificacao):
    """Cria a cobrança Pix. pagamento_id vira external_reference e chave de idempotência."""
    resp = requisitar(
        "POST",
        API + "/v1/payments",
        headers=_headers({"X-Idempotency-Key": pagamento_id}),
        json_corpo={
            "transaction_amount": float(valor),
            "description": descricao,
            "payment_method_id": "pix",
            "payer": {"email": email_pagador},
            "external_reference": pagamento_id,
            "notification_url": url_notificacao,
        },
    )
    dados = resp.get("point_of_interaction", {}).get("transaction_data", {})
    return {
        "id": str(resp["id"]),
        "qr_code": dados.get("qr_code"),
        "qr_code_base64": dados.get("qr_code_base64"),
        "ticket_url": dados.get("ticket_url"),
    }


def consultar(id_externo):
    return requisitar("GET", "{}/v1/payments/{}".format(API, id_externo), headers=_headers())


def assinatura_valida(x_signature, x_request_id, data_id, segredo):
    """Valida o cabeçalho x-signature ("ts=...,v1=...") das notificações do Mercado Pago."""
    if not x_signature or not data_id:
        return False
    partes = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    manifesto = "id:{};".format(str(data_id).lower())
    if x_request_id:
        manifesto += "request-id:{};".format(x_request_id)
    manifesto += "ts:{};".format(ts)
    esperado = hmac.new(segredo.encode("utf-8"), manifesto.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


# Status do Mercado Pago → status de pagamentos
STATUS = {
    "approved": "pago",
    "refunded": "estornado",
    "charged_back": "estornado",
}
