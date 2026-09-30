"""GET /api/validar_qrcode?c=<token>: endpoint público de autenticidade da certidão."""

import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))

from _lib import supabase, token_qr  # noqa: E402
from _lib.resposta import Handler  # noqa: E402


def validar(token):
    sid = token_qr.verificar(token)
    if not sid:
        return {"valida": False}
    sol = supabase.selecionar_um("solicitacoes_certidao", {
        "id": "eq." + sid,
        "status": "eq.aprovado",
        "select": "pdf_gerado_em,registro_vinculado_id",
    })
    if not sol or not sol.get("registro_vinculado_id") or not sol.get("pdf_gerado_em"):
        return {"valida": False}
    registro = supabase.selecionar_um("registros_sacramentais", {
        "id": "eq." + sol["registro_vinculado_id"],
        "select": "tipo,nome_pessoa,data_sacramento,paroquias(nome,dioceses(nome))",
    })
    if not registro:
        return {"valida": False}
    paroquia = registro["paroquias"]
    return {
        "valida": True,
        "certidao": {
            "tipo": registro["tipo"],
            "nome_pessoa": registro["nome_pessoa"],
            "data_sacramento": registro["data_sacramento"],
            "paroquia": paroquia["nome"],
            "diocese": paroquia["dioceses"]["nome"],
            "emitida_em": sol["pdf_gerado_em"],
        },
    }


class handler(Handler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        token = (query.get("c") or [""])[0]
        if not token:
            return self.responder(400, {"erro": "parâmetro c é obrigatório"})
        self.responder(200, validar(token))
