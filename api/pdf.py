"""POST /api/pdf: a paróquia vincula a solicitação ao registro oficial e emite a certidão.

Corpo (JSON), com o JWT do usuário paroquial em Authorization: Bearer <token>:
  {"solicitacao_id": "<uuid>", "registro_id": "<uuid>"}

O PDF é gerado só a partir de registros_sacramentais, nunca de dados_declarados.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from _lib import certidao_pdf, config, supabase, token_qr  # noqa: E402
from _lib.resposta import Handler  # noqa: E402


def processar(perfil, corpo):
    if not perfil or perfil["papel"] != "paroquial":
        return 403, {"erro": "apenas usuários paroquiais emitem certidões"}
    sid, rid = corpo.get("solicitacao_id"), corpo.get("registro_id")
    if not sid or not rid:
        return 400, {"erro": "solicitacao_id e registro_id são obrigatórios"}

    sol = supabase.selecionar_um("solicitacoes_certidao", {"id": "eq." + sid, "select": "*"})
    if not sol or sol["paroquia_id"] != perfil["paroquia_id"]:
        return 404, {"erro": "solicitação não encontrada"}
    if sol["status"] != "em_analise":
        return 409, {"erro": "a solicitação não está em análise"}

    registro = supabase.selecionar_um("registros_sacramentais", {"id": "eq." + rid, "select": "*"})
    if not registro or registro["paroquia_id"] != perfil["paroquia_id"]:
        return 404, {"erro": "registro não encontrado"}
    if registro["tipo"] != sol["tipo"]:
        return 409, {"erro": "o registro é de outro sacramento"}

    paroquia = supabase.selecionar_um("paroquias", {"id": "eq." + registro["paroquia_id"], "select": "*"})
    diocese = supabase.selecionar_um("dioceses", {"id": "eq." + paroquia["diocese_id"], "select": "*"})

    agora = datetime.now(timezone.utc)
    url_validacao = "{}/pages/validar.html?c={}".format(config.site_url(), token_qr.gerar(sid))
    conteudo = certidao_pdf.gerar_pdf(registro, paroquia, diocese, url_validacao, emitida_em=agora)

    # Primeiro o arquivo, depois o status: o email de aprovação já encontra o PDF.
    supabase.enviar_arquivo(
        config.BUCKET_CERTIDOES, "{}/{}.pdf".format(sol["solicitante_id"], sid), conteudo, "application/pdf"
    )
    atualizadas = supabase.atualizar(
        "solicitacoes_certidao",
        {"id": "eq." + sid, "status": "eq.em_analise"},
        {
            "registro_vinculado_id": rid,
            "status": "aprovado",
            "revisado_por": perfil["id"],
            "revisado_em": agora.isoformat(),
            "pdf_gerado_em": agora.isoformat(),
        },
    )
    if not atualizadas:
        return 409, {"erro": "a solicitação foi alterada por outra pessoa"}
    return 200, {"ok": True, "pdf_gerado_em": agora.isoformat()}


class handler(Handler):
    def do_POST(self):
        corpo = self.ler_json()
        if corpo is None:
            return self.responder(400, {"erro": "JSON inválido"})
        perfil = supabase.perfil_do_token(self.token_bearer())
        if not perfil:
            return self.responder(401, {"erro": "login necessário"})
        status, resposta = processar(perfil, corpo)
        self.responder(status, resposta)
