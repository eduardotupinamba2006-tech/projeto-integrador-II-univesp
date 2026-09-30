"""POST /api/cobranca_pix: gera a cobrança Pix de uma taxa de certidão ou de um dízimo.

Corpo (JSON), com o JWT do usuário em Authorization: Bearer <token>:
  {"tipo": "taxa_certidao", "solicitacao_id": "<uuid>"}
  {"tipo": "dizimo", "paroquia_id": "<uuid>", "valor": "50.00"}
"""

import os
import sys
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.dirname(__file__))

from _lib import config, mercadopago, supabase  # noqa: E402
from _lib.http import ErroHttp  # noqa: E402
from _lib.resposta import Handler  # noqa: E402

VALOR_MINIMO_DIZIMO = Decimal("1.00")
VALOR_MAXIMO_DIZIMO = Decimal("100000.00")


def valor_dizimo(bruto):
    """Converte e valida o valor do dízimo. Devolve Decimal ou None se inválido."""
    try:
        valor = Decimal(str(bruto))
    except (InvalidOperation, ValueError):
        return None
    if not valor.is_finite() or valor != valor.quantize(Decimal("0.01")):
        return None
    if valor < VALOR_MINIMO_DIZIMO or valor > VALOR_MAXIMO_DIZIMO:
        return None
    return valor


def _resposta_pix(pagamento, pix):
    return {
        "pagamento_id": pagamento["id"],
        "valor": str(pagamento["valor"]),
        "qr_code": pix.get("qr_code"),
        "qr_code_base64": pix.get("qr_code_base64"),
        "ticket_url": pix.get("ticket_url"),
    }


def _pix_existente(pagamento):
    """Reapresenta a cobrança Pix de um pagamento pendente já criado."""
    dados = mercadopago.consultar(pagamento["id_transacao_externa"])
    tx = dados.get("point_of_interaction", {}).get("transaction_data", {})
    return {"qr_code": tx.get("qr_code"), "qr_code_base64": tx.get("qr_code_base64"), "ticket_url": tx.get("ticket_url")}


def _cobrar(pagamento, descricao, email):
    pix = mercadopago.criar_pix(
        pagamento["id"], pagamento["valor"], descricao, email, config.site_url() + "/api/webhook_pagamento"
    )
    supabase.atualizar("pagamentos", {"id": "eq." + pagamento["id"]}, {"id_transacao_externa": pix["id"]})
    return pix


def processar(perfil, email, corpo):
    tipo = corpo.get("tipo")

    if tipo == "taxa_certidao":
        sid = corpo.get("solicitacao_id")
        if not sid:
            return 400, {"erro": "solicitacao_id é obrigatório"}
        sol = supabase.selecionar_um("solicitacoes_certidao", {"id": "eq." + sid, "select": "*"})
        if not sol or sol["solicitante_id"] != perfil["id"]:
            return 404, {"erro": "solicitação não encontrada"}
        if sol["status"] != "aguardando_pagamento":
            return 409, {"erro": "esta solicitação não está aguardando pagamento"}

        if sol.get("pagamento_id"):
            pagamento = supabase.selecionar_um("pagamentos", {"id": "eq." + sol["pagamento_id"], "select": "*"})
            if pagamento.get("id_transacao_externa"):
                return 200, _resposta_pix(pagamento, _pix_existente(pagamento))
        else:
            pagamento = supabase.inserir("pagamentos", {
                "tipo": "taxa_certidao",
                "paroquia_id": sol["paroquia_id"],
                "usuario_id": perfil["id"],
                "valor": str(config.TAXA_CERTIDAO),
            })
            supabase.atualizar("solicitacoes_certidao", {"id": "eq." + sid}, {"pagamento_id": pagamento["id"]})
        pix = _cobrar(pagamento, "Taxa de emissão de certidão", email)
        return 200, _resposta_pix(pagamento, pix)

    if tipo == "dizimo":
        valor = valor_dizimo(corpo.get("valor"))
        if valor is None:
            return 400, {"erro": "valor inválido: informe entre R$ 1,00 e R$ 100.000,00"}
        pid = corpo.get("paroquia_id") or ""
        if not supabase.selecionar_um("paroquias", {"id": "eq." + pid, "select": "id"}):
            return 404, {"erro": "paróquia não encontrada"}
        # Valor integral: o dízimo não tem taxa do sistema.
        pagamento = supabase.inserir("pagamentos", {
            "tipo": "dizimo",
            "paroquia_id": pid,
            "usuario_id": perfil["id"],
            "valor": str(valor),
        })
        pix = _cobrar(pagamento, "Dízimo", email)
        return 200, _resposta_pix(pagamento, pix)

    return 400, {"erro": "tipo deve ser taxa_certidao ou dizimo"}


class handler(Handler):
    def do_POST(self):
        corpo = self.ler_json()
        if corpo is None:
            return self.responder(400, {"erro": "JSON inválido"})
        usuario = supabase.usuario_do_token(self.token_bearer())
        if not usuario:
            return self.responder(401, {"erro": "login necessário"})
        perfil = supabase.selecionar_um("perfis", {"auth_user_id": "eq." + usuario["id"], "select": "*"})
        if not perfil:
            return self.responder(403, {"erro": "perfil não encontrado"})
        try:
            status, resposta = processar(perfil, usuario["email"], corpo)
        except ErroHttp:
            return self.responder(502, {"erro": "falha ao gerar a cobrança Pix, tente novamente"})
        self.responder(status, resposta)
