"""POST /api/webhook_pagamento: notificação do Mercado Pago.

O corpo da notificação só informa o id; o status real é sempre consultado na API
do Mercado Pago antes de alterar qualquer coisa.
"""

import json
import os
import sys
import urllib.parse
from decimal import Decimal

sys.path.insert(0, os.path.dirname(__file__))

from _lib import config, mercadopago, supabase  # noqa: E402
from _lib.resposta import Handler  # noqa: E402


def processar_pagamento(id_externo):
    dados = mercadopago.consultar(id_externo)
    novo_status = mercadopago.STATUS.get(dados.get("status"))
    if not novo_status:
        return 200, {"ignorado": "status " + str(dados.get("status"))}

    pagamento = supabase.selecionar_um(
        "pagamentos", {"id": "eq." + str(dados.get("external_reference") or ""), "select": "*"}
    )
    if not pagamento or pagamento.get("id_transacao_externa") not in (None, str(id_externo)):
        return 404, {"erro": "pagamento não encontrado"}
    if Decimal(str(dados.get("transaction_amount"))) != Decimal(str(pagamento["valor"])):
        return 409, {"erro": "valor divergente"}
    if pagamento["status"] == novo_status:
        return 200, {"ok": True, "idempotente": True}

    supabase.atualizar(
        "pagamentos",
        {"id": "eq." + pagamento["id"], "status": "eq." + pagamento["status"]},
        {"status": novo_status, "id_transacao_externa": str(id_externo)},
    )

    if novo_status == "pago" and pagamento["tipo"] == "taxa_certidao":
        supabase.atualizar(
            "solicitacoes_certidao",
            {"pagamento_id": "eq." + pagamento["id"], "status": "eq.aguardando_pagamento"},
            {"status": "em_analise"},
        )

    if novo_status == "pago" and pagamento["tipo"] == "dizimo":
        dizimista = supabase.selecionar_um("dizimistas", {
            "perfil_id": "eq." + pagamento["usuario_id"],
            "paroquia_id": "eq." + pagamento["paroquia_id"],
            "select": "id",
        })
        ja_existe = supabase.selecionar_um("doacoes", {"pagamento_id": "eq." + pagamento["id"], "select": "id"})
        if dizimista and not ja_existe:
            supabase.inserir("doacoes", {
                "dizimista_id": dizimista["id"],
                "paroquia_id": pagamento["paroquia_id"],
                "pagamento_id": pagamento["id"],
            })

    return 200, {"ok": True, "status": novo_status}


class handler(Handler):
    def do_POST(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        bruto = self.ler_corpo_bruto()
        try:
            corpo = json.loads(bruto or b"{}")
        except ValueError:
            corpo = {}
        tipo = (query.get("type") or [corpo.get("type")])[0]
        data_id = (query.get("data.id") or [(corpo.get("data") or {}).get("id")])[0]

        if not mercadopago.assinatura_valida(
            self.headers.get("x-signature"), self.headers.get("x-request-id"), data_id,
            config.obrigatoria("MP_WEBHOOK_SECRET"),
        ):
            return self.responder(401, {"erro": "assinatura inválida"})
        if tipo != "payment":
            return self.responder(200, {"ignorado": tipo})

        status, resposta = processar_pagamento(data_id)
        self.responder(status, resposta)
