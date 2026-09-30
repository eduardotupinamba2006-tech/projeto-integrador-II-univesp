"""Fixtures e helpers dos testes de isolamento de RLS.

Os testes conectam direto no Postgres do Supabase local (DATABASE_URL,
padrão postgresql://postgres:postgres@127.0.0.1:54322/postgres). Cada teste
roda dentro de uma transação que sofre ROLLBACK no fim, então nada persiste
e os testes não dependem do supabase/seed.sql.

Os dados do cenário são criados como `postgres` (dono das tabelas, ignora
RLS). Para agir como um usuário final, use `como(cur, usuario)`,
`como_anon(cur)` e, para voltar, `como_postgres(cur)`.
"""

import json
import os
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

try:
    import psycopg
    from psycopg import errors
except ImportError:  # pragma: no cover - só sem as dependências de dev
    psycopg = None
    errors = None

URL_PADRAO = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"


def pular_ou_falhar(motivo):
    """Localmente pula; no CI (variável CI definida) falha, para não passar verde sem banco."""
    if os.environ.get("CI"):
        pytest.fail(motivo, pytrace=False)
    pytest.skip(motivo)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "rls: testes de isolamento de Row Level Security (exigem o Supabase local)",
    )


# ---------------------------------------------------------------------------
# Conexão e transação por teste
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def conexao():
    if psycopg is None:
        pular_ou_falhar("psycopg não instalado: rode `py -m pip install -r requirements-dev.txt`")
    url = os.environ.get("DATABASE_URL", URL_PADRAO)
    try:
        conn = psycopg.connect(url, connect_timeout=3)
    except psycopg.OperationalError as erro:
        detalhe = (str(erro).strip().splitlines() or [""])[0]
        pular_ou_falhar(
            "Banco do Supabase local inacessível. Rode `supabase start` "
            "ou defina DATABASE_URL. Detalhe: {}".format(detalhe)
        )
    with conn.cursor() as cur:
        cur.execute("select to_regclass('public.solicitacoes_certidao') is not null")
        tem_schema = cur.fetchone()[0]
    conn.rollback()
    if not tem_schema:
        conn.close()
        pular_ou_falhar("Schema não encontrado: aplique as migrations (`supabase db reset`).")
    yield conn
    conn.close()


@pytest.fixture
def cur(conexao):
    """Cursor dentro de uma transação que é desfeita no fim do teste."""
    cursor = conexao.cursor()
    # Abre a transação implícita já aqui, para que `conexao.transaction()`
    # dentro dos testes crie SAVEPOINTs (e não uma transação que faz COMMIT).
    cursor.execute("select 1")
    try:
        yield cursor
    finally:
        cursor.close()
        conexao.rollback()


# ---------------------------------------------------------------------------
# Troca de papel
# ---------------------------------------------------------------------------


def como_postgres(cur):
    cur.execute("reset role")
    cur.execute("select set_config('request.jwt.claims', '', true)")


def como(cur, usuario):
    """Passa a agir como o usuário autenticado (SimpleNamespace com auth_id)."""
    cur.execute("reset role")
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"sub": str(usuario.auth_id), "role": "authenticated"}),),
    )
    cur.execute("set local role authenticated")


def como_anon(cur):
    cur.execute("reset role")
    cur.execute(
        "select set_config('request.jwt.claims', %s, true)",
        (json.dumps({"role": "anon"}),),
    )
    cur.execute("set local role anon")


@contextmanager
def espera_erro(cur, erro=None):
    """Espera que o bloco levante `erro` (padrão: 42501 InsufficientPrivilege).

    O bloco roda num SAVEPOINT, então a transação do teste continua usável.
    """
    if erro is None:
        erro = errors.InsufficientPrivilege
    with pytest.raises(erro) as info:
        with cur.connection.transaction():
            yield info


# ---------------------------------------------------------------------------
# Consultas curtas
# ---------------------------------------------------------------------------


def ids_visiveis(cur, tabela, coluna="id"):
    cur.execute("select {} from public.{}".format(coluna, tabela))
    return {linha[0] for linha in cur.fetchall()}


def valor(cur, sql, params=None):
    cur.execute(sql, params)
    linha = cur.fetchone()
    return None if linha is None else linha[0]


# ---------------------------------------------------------------------------
# Cenário sintético
# ---------------------------------------------------------------------------


def _inserir(cur, sql, params):
    cur.execute(sql + " returning id", params)
    return cur.fetchone()[0]


def _criar_usuario(cur, apelido):
    auth_id = uuid.uuid4()
    email = "{}.{}@teste.invalid".format(apelido, auth_id.hex[:8])
    meta = json.dumps({"nome": "Fulano Teste {}".format(apelido), "cpf": "000"})
    cur.execute(
        "insert into auth.users (id, instance_id, aud, role, email, raw_user_meta_data) "
        "values (%s, '00000000-0000-0000-0000-000000000000', 'authenticated', "
        "'authenticated', %s, %s)",
        (auth_id, email, meta),
    )
    perfil_id = valor(cur, "select id from public.perfis where auth_user_id = %s", (auth_id,))
    assert perfil_id is not None, "trigger ao_criar_usuario não criou o perfil"
    return SimpleNamespace(apelido=apelido, auth_id=auth_id, perfil_id=perfil_id)


def _promover(cur, usuario, papel, paroquia_id=None, diocese_id=None):
    cur.execute(
        "update public.perfis set papel = %s, paroquia_id = %s, diocese_id = %s where id = %s",
        (papel, paroquia_id, diocese_id, usuario.perfil_id),
    )


@pytest.fixture
def cenario(cur):
    """Cria, como postgres, duas dioceses, três paróquias, sete usuários e
    registros espalhados. Tudo é desfeito no fim do teste."""
    como_postgres(cur)
    c = SimpleNamespace()

    c.alfa = _inserir(cur, "insert into public.dioceses (nome, uf) values (%s, %s)", ("Diocese Teste Alfa", "ZZ"))
    c.beta = _inserir(cur, "insert into public.dioceses (nome, uf) values (%s, %s)", ("Diocese Teste Beta", "ZZ"))
    sql_paroquia = "insert into public.paroquias (diocese_id, nome, endereco) values (%s, %s, %s)"
    c.a1 = _inserir(cur, sql_paroquia, (c.alfa, "Paróquia Teste A1", "Rua Fictícia, 1"))
    c.a2 = _inserir(cur, sql_paroquia, (c.alfa, "Paróquia Teste A2", "Rua Fictícia, 2"))
    c.b1 = _inserir(cur, sql_paroquia, (c.beta, "Paróquia Teste B1", "Rua Fictícia, 3"))
    c.paroquias = {c.a1, c.a2, c.b1}

    c.publico1 = _criar_usuario(cur, "publico1")
    c.publico2 = _criar_usuario(cur, "publico2")
    c.paroquial_A1 = _criar_usuario(cur, "paroquial_A1")
    c.paroquial_A2 = _criar_usuario(cur, "paroquial_A2")
    c.paroquial_B1 = _criar_usuario(cur, "paroquial_B1")
    c.diocesano_Alfa = _criar_usuario(cur, "diocesano_Alfa")
    c.diocesano_Beta = _criar_usuario(cur, "diocesano_Beta")
    _promover(cur, c.paroquial_A1, "paroquial", paroquia_id=c.a1)
    _promover(cur, c.paroquial_A2, "paroquial", paroquia_id=c.a2)
    _promover(cur, c.paroquial_B1, "paroquial", paroquia_id=c.b1)
    _promover(cur, c.diocesano_Alfa, "diocesano", diocese_id=c.alfa)
    _promover(cur, c.diocesano_Beta, "diocesano", diocese_id=c.beta)

    # registros_sacramentais: dois na A1, um na A2, um na B1.
    sql_registro = (
        "insert into public.registros_sacramentais "
        "(paroquia_id, tipo, nome_pessoa, data_sacramento, criado_por) values (%s, %s, %s, %s, %s)"
    )
    c.reg_A1 = _inserir(cur, sql_registro, (c.a1, "batismo", "Beltrano Fictício A1", "2000-01-01", c.paroquial_A1.perfil_id))
    c.reg_A1_b = _inserir(cur, sql_registro, (c.a1, "crisma", "Sicrano Fictício A1", "2010-01-01", c.paroquial_A1.perfil_id))
    c.reg_A2 = _inserir(cur, sql_registro, (c.a2, "batismo", "Beltrano Fictício A2", "2001-01-01", c.paroquial_A2.perfil_id))
    c.reg_B1 = _inserir(cur, sql_registro, (c.b1, "casamento", "Beltrano Fictício B1", "2002-01-01", c.paroquial_B1.perfil_id))
    c.registros = {c.reg_A1, c.reg_A1_b, c.reg_A2, c.reg_B1}

    # pagamentos
    sql_pagamento = (
        "insert into public.pagamentos (tipo, paroquia_id, usuario_id, valor, status) "
        "values (%s, %s, %s, %s, %s)"
    )
    c.pag_p1_A1_dizimo = _inserir(cur, sql_pagamento, ("dizimo", c.a1, c.publico1.perfil_id, 50, "pago"))
    c.pag_p1_A1_taxa = _inserir(cur, sql_pagamento, ("taxa_certidao", c.a1, c.publico1.perfil_id, 20, "pendente"))
    c.pag_p2_A2_dizimo = _inserir(cur, sql_pagamento, ("dizimo", c.a2, c.publico2.perfil_id, 30, "pago"))
    c.pag_p2_B1_dizimo = _inserir(cur, sql_pagamento, ("dizimo", c.b1, c.publico2.perfil_id, 40, "pago"))
    c.pagamentos = {c.pag_p1_A1_dizimo, c.pag_p1_A1_taxa, c.pag_p2_A2_dizimo, c.pag_p2_B1_dizimo}

    # dizimistas
    sql_dizimista = "insert into public.dizimistas (perfil_id, paroquia_id) values (%s, %s)"
    c.diz_p1_A1 = _inserir(cur, sql_dizimista, (c.publico1.perfil_id, c.a1))
    c.diz_p2_A2 = _inserir(cur, sql_dizimista, (c.publico2.perfil_id, c.a2))
    c.diz_p2_B1 = _inserir(cur, sql_dizimista, (c.publico2.perfil_id, c.b1))
    c.dizimistas = {c.diz_p1_A1, c.diz_p2_A2, c.diz_p2_B1}

    # doacoes
    sql_doacao = "insert into public.doacoes (dizimista_id, paroquia_id, pagamento_id) values (%s, %s, %s)"
    c.doa_p1_A1 = _inserir(cur, sql_doacao, (c.diz_p1_A1, c.a1, c.pag_p1_A1_dizimo))
    c.doa_p2_A2 = _inserir(cur, sql_doacao, (c.diz_p2_A2, c.a2, c.pag_p2_A2_dizimo))
    c.doa_p2_B1 = _inserir(cur, sql_doacao, (c.diz_p2_B1, c.b1, c.pag_p2_B1_dizimo))
    c.doacoes = {c.doa_p1_A1, c.doa_p2_A2, c.doa_p2_B1}

    # solicitacoes_certidao
    sql_solicitacao = (
        "insert into public.solicitacoes_certidao "
        "(solicitante_id, paroquia_id, tipo, dados_declarados, status, pagamento_id) "
        "values (%s, %s, %s, %s, %s, %s)"
    )
    dados = json.dumps({"nome": "Beltrano Fictício", "data_aproximada": "2000"})
    c.sol_p1_A1_aguardando = _inserir(cur, sql_solicitacao, (c.publico1.perfil_id, c.a1, "batismo", dados, "aguardando_pagamento", None))
    c.sol_p1_A1_analise = _inserir(cur, sql_solicitacao, (c.publico1.perfil_id, c.a1, "batismo", dados, "em_analise", c.pag_p1_A1_taxa))
    c.sol_p2_A2_analise = _inserir(cur, sql_solicitacao, (c.publico2.perfil_id, c.a2, "crisma", dados, "em_analise", None))
    c.sol_p2_B1_analise = _inserir(cur, sql_solicitacao, (c.publico2.perfil_id, c.b1, "casamento", dados, "em_analise", None))
    c.solicitacoes = {c.sol_p1_A1_aguardando, c.sol_p1_A1_analise, c.sol_p2_A2_analise, c.sol_p2_B1_analise}

    # emails_enviados (só para provar que existe linha e ninguém a vê)
    c.email = _inserir(
        cur,
        "insert into public.emails_enviados (destinatario_email, tipo, status_envio) values (%s, %s, %s)",
        ("ninguem@teste.invalid", "teste", "enviado"),
    )

    return c
