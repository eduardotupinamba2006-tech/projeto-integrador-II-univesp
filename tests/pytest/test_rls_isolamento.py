"""RLS: perfis, dioceses/paróquias, emails_enviados e acesso anônimo."""

import pytest

from conftest import como, como_anon, como_postgres, espera_erro, ids_visiveis, valor

pytestmark = pytest.mark.rls

TODOS_AUTENTICADOS = [
    "publico1",
    "publico2",
    "paroquial_A1",
    "paroquial_A2",
    "paroquial_B1",
    "diocesano_Alfa",
    "diocesano_Beta",
]


def agir_como(cur, cenario, quem):
    if quem == "anon":
        como_anon(cur)
    else:
        como(cur, getattr(cenario, quem))


# ---------------------------------------------------------------------------
# perfis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("quem", TODOS_AUTENTICADOS)
def test_perfis_cada_usuario_ve_so_o_proprio(cur, cenario, quem):
    usuario = getattr(cenario, quem)
    como(cur, usuario)
    assert ids_visiveis(cur, "perfis") == {usuario.perfil_id}


def test_perfis_nao_edita_perfil_de_outro(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute("update public.perfis set nome = 'Invasor' where id = %s", (cenario.publico2.perfil_id,))
    assert cur.rowcount == 0

    como_postgres(cur)
    nome = valor(cur, "select nome from public.perfis where id = %s", (cenario.publico2.perfil_id,))
    assert nome != "Invasor"


def test_perfis_paroquial_nao_edita_perfil_de_publico(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute("update public.perfis set nome = 'Invasor' where id = %s", (cenario.publico1.perfil_id,))
    assert cur.rowcount == 0


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1", "diocesano_Alfa"])
@pytest.mark.parametrize("coluna", ["papel", "paroquia_id", "diocese_id"])
def test_perfis_nao_altera_proprio_papel_nem_vinculo(cur, cenario, quem, coluna):
    usuario = getattr(cenario, quem)
    novo_valor = {"papel": "diocesano", "paroquia_id": cenario.b1, "diocese_id": cenario.beta}[coluna]
    if quem == "diocesano_Alfa" and coluna == "papel":
        novo_valor = "paroquial"

    como(cur, usuario)
    with espera_erro(cur):
        cur.execute(
            "update public.perfis set {} = %s where id = %s".format(coluna),
            (novo_valor, usuario.perfil_id),
        )

    como_postgres(cur)
    atual = valor(cur, "select {} from public.perfis where id = %s".format(coluna), (usuario.perfil_id,))
    assert atual != novo_valor


def test_perfis_altera_proprio_nome(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute("update public.perfis set nome = 'Fulano Renomeado' where id = %s", (cenario.publico1.perfil_id,))
    assert cur.rowcount == 1

    como_postgres(cur)
    assert valor(cur, "select nome from public.perfis where id = %s", (cenario.publico1.perfil_id,)) == "Fulano Renomeado"


def test_perfis_usuario_nao_cria_perfil(cur, cenario):
    como(cur, cenario.publico1)
    with espera_erro(cur):
        cur.execute(
            "insert into public.perfis (auth_user_id, nome, cpf, papel) values (%s, 'Outro', '000', 'diocesano')",
            (cenario.publico1.auth_id,),
        )


# ---------------------------------------------------------------------------
# dioceses e paróquias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tabela", ["dioceses", "paroquias"])
@pytest.mark.parametrize("quem", ["anon"] + TODOS_AUTENTICADOS)
def test_dioceses_paroquias_leitura_publica(cur, cenario, tabela, quem):
    como_postgres(cur)
    todas = ids_visiveis(cur, tabela)
    esperadas = {cenario.alfa, cenario.beta} if tabela == "dioceses" else cenario.paroquias
    assert esperadas <= todas

    agir_como(cur, cenario, quem)
    assert ids_visiveis(cur, tabela) == todas


@pytest.mark.parametrize("quem", ["anon", "publico1", "paroquial_A1", "diocesano_Alfa"])
def test_dioceses_ninguem_escreve(cur, cenario, quem):
    agir_como(cur, cenario, quem)
    with espera_erro(cur):
        cur.execute("insert into public.dioceses (nome, uf) values ('Diocese Invasora', 'ZZ')")

    cur.execute("update public.dioceses set nome = 'Alterada' where id = %s", (cenario.alfa,))
    assert cur.rowcount == 0
    cur.execute("delete from public.dioceses where id = %s", (cenario.beta,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select nome from public.dioceses where id = %s", (cenario.alfa,)) == "Diocese Teste Alfa"
    assert valor(cur, "select count(*) from public.dioceses where id = %s", (cenario.beta,)) == 1


@pytest.mark.parametrize("quem", ["anon", "publico1", "paroquial_A1", "diocesano_Alfa"])
def test_paroquias_ninguem_escreve(cur, cenario, quem):
    agir_como(cur, cenario, quem)
    with espera_erro(cur):
        cur.execute(
            "insert into public.paroquias (diocese_id, nome, endereco) values (%s, 'Paróquia Invasora', 'Rua X')",
            (cenario.alfa,),
        )

    cur.execute("update public.paroquias set nome = 'Alterada' where id = %s", (cenario.a1,))
    assert cur.rowcount == 0
    cur.execute("delete from public.paroquias where id = %s", (cenario.b1,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select nome from public.paroquias where id = %s", (cenario.a1,)) == "Paróquia Teste A1"
    assert valor(cur, "select count(*) from public.paroquias where id = %s", (cenario.b1,)) == 1


# ---------------------------------------------------------------------------
# emails_enviados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("quem", ["anon"] + TODOS_AUTENTICADOS)
def test_emails_ninguem_le(cur, cenario, quem):
    agir_como(cur, cenario, quem)
    assert ids_visiveis(cur, "emails_enviados") == set()


@pytest.mark.parametrize("quem", ["anon", "publico1", "paroquial_A1", "diocesano_Alfa"])
def test_emails_ninguem_insere(cur, cenario, quem):
    agir_como(cur, cenario, quem)
    with espera_erro(cur):
        cur.execute(
            "insert into public.emails_enviados (destinatario_email, tipo, status_envio) "
            "values ('alguem@teste.invalid', 'teste', 'enviado')"
        )


# ---------------------------------------------------------------------------
# anon
# ---------------------------------------------------------------------------

TABELAS_PRIVADAS = [
    "perfis",
    "registros_sacramentais",
    "pagamentos",
    "dizimistas",
    "doacoes",
    "solicitacoes_certidao",
]


@pytest.mark.parametrize("tabela", TABELAS_PRIVADAS)
def test_anon_nao_le_tabelas_privadas(cur, cenario, tabela):
    como_postgres(cur)
    assert valor(cur, "select count(*) from public.{}".format(tabela)) > 0

    como_anon(cur)
    assert ids_visiveis(cur, tabela) == set()


@pytest.mark.parametrize("tabela", TABELAS_PRIVADAS)
def test_anon_nao_edita_nem_apaga(cur, cenario, tabela):
    como_postgres(cur)
    antes = valor(cur, "select count(*) from public.{}".format(tabela))

    como_anon(cur)
    # "update ... set id = id" não muda nada, mas prova que nenhuma linha é alcançável.
    cur.execute("update public.{} set id = id".format(tabela))
    assert cur.rowcount == 0
    cur.execute("delete from public.{}".format(tabela))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select count(*) from public.{}".format(tabela)) == antes


def test_anon_nao_cria_solicitacao(cur, cenario):
    como_anon(cur)
    with espera_erro(cur):
        cur.execute(
            "insert into public.solicitacoes_certidao (solicitante_id, paroquia_id, tipo, dados_declarados) "
            "values (%s, %s, 'batismo', '{}')",
            (cenario.publico1.perfil_id, cenario.a1),
        )
