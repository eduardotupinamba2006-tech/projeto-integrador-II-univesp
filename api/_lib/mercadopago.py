"""Pix pela API de Orders do Mercado Pago (sandbox enquanto MP_ACCESS_TOKEN for de uma conta de teste)."""

import hashlib
import hmac
import time

from . import config
from .http import requisitar

API = "https://api.mercadopago.com"


def _headers(extra=None):
    h = {"Authorization": "Bearer " + config.obrigatoria("MP_ACCESS_TOKEN")}
    h.update(extra or {})
    return h


def _dados_pix(order):
    """Resume a order: status, referência, valor e os dados do QR Code do Pix."""
    pagamento = (order.get("transactions", {}).get("payments") or [{}])[0]
    metodo = pagamento.get("payment_method", {})
    return {
        "id": str(order["id"]),
        "status": order.get("status"),
        "external_reference": order.get("external_reference"),
        "valor": order.get("total_amount"),
        "qr_code": metodo.get("qr_code"),
        "qr_code_base64": metodo.get("qr_code_base64"),
        "ticket_url": metodo.get("ticket_url"),
    }


def criar_pix(pagamento_id, valor, descricao, pagador):
    """Cria a cobrança Pix pela API de Orders.

    pagamento_id vira external_reference e chave de idempotência. A URL das
    notificações não vai na requisição: a API de Orders usa a do painel da aplicação.
    """
    valor = "{:.2f}".format(valor) if not isinstance(valor, str) else valor
    order = requisitar(
        "POST",
        API + "/v1/orders",
        headers=_headers({"X-Idempotency-Key": pagamento_id}),
        json_corpo={
            "type": "online",
            "processing_mode": "automatic",
            "total_amount": valor,
            "description": descricao,
            "external_reference": pagamento_id,
            "payer": pagador,
            "transactions": {"payments": [{"amount": valor, "payment_method": {"id": "pix", "type": "bank_transfer"}}]},
        },
    )
    pix = _dados_pix(order)
    # A order às vezes nasce "processing", e o QR Code chega alguns instantes depois.
    for _ in range(4):
        if pix["qr_code"] or pix["status"] not in ("created", "processing"):
            break
        time.sleep(1)
        pix = consultar(pix["id"])
    return pix


def consultar(id_externo):
    return _dados_pix(requisitar("GET", "{}/v1/orders/{}".format(API, id_externo), headers=_headers()))


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


# Status da order no Mercado Pago → status de pagamentos
STATUS = {
    "processed": "pago",
    "refunded": "estornado",
    "charged_back": "estornado",
}
