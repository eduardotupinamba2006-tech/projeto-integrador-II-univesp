"""Acesso ao Supabase com a service role (ignora RLS: validar permissões antes de usar)."""

import urllib.parse

from . import config
from .http import ErroHttp, requisitar


def _headers(extra=None):
    chave = config.obrigatoria("SUPABASE_SERVICE_ROLE_KEY")
    h = {"apikey": chave, "Authorization": "Bearer " + chave}
    h.update(extra or {})
    return h


def _rest(tabela, filtros=None):
    url = "{}/rest/v1/{}".format(config.supabase_url(), tabela)
    if filtros:
        url += "?" + urllib.parse.urlencode(filtros)
    return url


def selecionar(tabela, filtros):
    """filtros no formato PostgREST, ex.: {"id": "eq.<uuid>", "select": "*"}."""
    return requisitar("GET", _rest(tabela, filtros), headers=_headers())


def selecionar_um(tabela, filtros):
    linhas = selecionar(tabela, filtros)
    return linhas[0] if linhas else None


def inserir(tabela, linha):
    linhas = requisitar(
        "POST", _rest(tabela), headers=_headers({"Prefer": "return=representation"}), json_corpo=linha
    )
    return linhas[0]


def atualizar(tabela, filtros, valores):
    return requisitar(
        "PATCH", _rest(tabela, filtros), headers=_headers({"Prefer": "return=representation"}), json_corpo=valores
    )


def usuario_do_token(jwt):
    """Valida o JWT do usuário no Supabase Auth. Devolve o usuário ou None."""
    if not jwt:
        return None
    try:
        return requisitar(
            "GET",
            config.supabase_url() + "/auth/v1/user",
            headers={"apikey": config.obrigatoria("SUPABASE_SERVICE_ROLE_KEY"), "Authorization": "Bearer " + jwt},
        )
    except ErroHttp:
        return None


def perfil_do_token(jwt):
    usuario = usuario_do_token(jwt)
    if not usuario:
        return None
    return selecionar_um("perfis", {"auth_user_id": "eq." + usuario["id"], "select": "*"})


def email_do_perfil(perfil_id):
    perfil = selecionar_um("perfis", {"id": "eq." + perfil_id, "select": "auth_user_id,nome"})
    if not perfil:
        return None, None
    usuario = requisitar(
        "GET", "{}/auth/v1/admin/users/{}".format(config.supabase_url(), perfil["auth_user_id"]), headers=_headers()
    )
    return usuario.get("email"), perfil["nome"]


def enviar_arquivo(bucket, caminho, conteudo, tipo):
    requisitar(
        "POST",
        "{}/storage/v1/object/{}/{}".format(config.supabase_url(), bucket, caminho),
        headers=_headers({"Content-Type": tipo, "x-upsert": "true"}),
        dados=conteudo,
    )


def url_assinada(bucket, caminho, segundos):
    resp = requisitar(
        "POST",
        "{}/storage/v1/object/sign/{}/{}".format(config.supabase_url(), bucket, caminho),
        headers=_headers(),
        json_corpo={"expiresIn": segundos},
    )
    return config.supabase_url() + "/storage/v1" + resp["signedURL"]
