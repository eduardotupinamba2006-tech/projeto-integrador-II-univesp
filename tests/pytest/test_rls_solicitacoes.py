"""RLS e travas de coluna: solicitacoes_certidao."""

import json

import pytest

from conftest import como, como_postgres, errors, espera_erro, ids_visiveis, valor

pytestmark = pytest.mark.rls


def estado(cur, solicitacao_id):
    """Lê (como postgres) as colunas relevantes de uma solicitação."""
    como_postgres(cur)
    cur.execute(
        "select status, motivo_rejeicao, revisado_por, revisado_em, registro_vinculado_id, "
        "paroquia_id, dados_declarados from public.solicitacoes_certidao where id = %s",
        (solicitacao_id,),
    )
    colunas = [d.name for d in cur.description]
    return dict(zip(colunas, cur.fetchone()))


def inserir_solicitacao(cur, cenario, **extras):
    colunas = {
        "solicitante_id": cenario.publico1.perfil_id,
        "paroquia_id": cenario.a1,
        "tipo": "batismo",
        "dados_declarados": json.dumps({"nome": "Fulano Fictício"}),
    }
    colunas.update(extras)
    nomes = ", ".join(colunas)
    marcadores = ", ".join(["%s"] * len(colunas))
    cur.execute(
        "insert into public.solicitacoes_certidao ({}) values ({}) returning id, status, solicitante_id".format(
            nomes, marcadores
        ),
        list(colunas.values()),
    )
    return cur.fetchone()


# ---------------------------------------------------------------------------
# público (solicitante)
# ---------------------------------------------------------------------------


def test_publico_cria_para_si_aguardando_pagamento(cur, cenario):
    como(cur, cenario.publico1)
    _, status, solicitante = inserir_solicitacao(cur, cenario)
    assert status == "aguardando_pagamento"
    assert solicitante == cenario.publico1.perfil_id


def test_publico_cria_com_status_explicito_aguardando_pagamento(cur, cenario):
    como(cur, cenario.publico1)
    _, status, _ = inserir_solicitacao(cur, cenario, status="aguardando_pagamento")
    assert status == "aguardando_pagamento"


@pytest.mark.parametrize(
    "caso",
    ["outro_solicitante", "em_analise", "aprovado", "rejeitado", "registro_vinculado", "pagamento"],
)
def test_publico_nao_cria_solicitacao_irregular(cur, cenario, caso):
    extras = {
        "outro_solicitante": {"solicitante_id": cenario.publico2.perfil_id},
        "em_analise": {"status": "em_analise"},
        "aprovado": {"status": "aprovado"},
        "rejeitado": {"status": "rejeitado", "motivo_rejeicao": "x"},
        "registro_vinculado": {"registro_vinculado_id": cenario.reg_A1},
        "pagamento": {"pagamento_id": cenario.pag_p1_A1_taxa},
    }[caso]
    como(cur, cenario.publico1)
    with espera_erro(cur):
        inserir_solicitacao(cur, cenario, **extras)


def test_publico_le_so_as_proprias(cur, cenario):
    como(cur, cenario.publico1)
    assert ids_visiveis(cur, "solicitacoes_certidao") == {cenario.sol_p1_A1_aguardando, cenario.sol_p1_A1_analise}

    como(cur, cenario.publico2)
    assert ids_visiveis(cur, "solicitacoes_certidao") == {cenario.sol_p2_A2_analise, cenario.sol_p2_B1_analise}


def test_publico_altera_dados_declarados_enquanto_aguardando(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute(
        "update public.solicitacoes_certidao set dados_declarados = %s where id = %s",
        (json.dumps({"nome": "Nome Corrigido"}), cenario.sol_p1_A1_aguardando),
    )
    assert cur.rowcount == 1
    assert estado(cur, cenario.sol_p1_A1_aguardando)["dados_declarados"] == {"nome": "Nome Corrigido"}


def test_publico_nao_altera_dados_declarados_depois_do_pagamento(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute(
        "update public.solicitacoes_certidao set dados_declarados = %s where id = %s",
        (json.dumps({"nome": "Nome Corrigido"}), cenario.sol_p1_A1_analise),
    )
    assert cur.rowcount == 0
    assert estado(cur, cenario.sol_p1_A1_analise)["dados_declarados"] != {"nome": "Nome Corrigido"}


@pytest.mark.parametrize("coluna", ["status", "registro_vinculado_id", "paroquia_id"])
def test_publico_nao_altera_campos_protegidos(cur, cenario, coluna):
    novo_valor = {"status": "em_analise", "registro_vinculado_id": cenario.reg_A1, "paroquia_id": cenario.a2}[coluna]
    como(cur, cenario.publico1)
    with espera_erro(cur):
        cur.execute(
            "update public.solicitacoes_certidao set {} = %s where id = %s".format(coluna),
            (novo_valor, cenario.sol_p1_A1_aguardando),
        )

    antes = estado(cur, cenario.sol_p1_A1_aguardando)
    assert antes[coluna] != novo_valor
    assert antes["status"] == "aguardando_pagamento"


def test_publico_nao_edita_solicitacao_de_outro(cur, cenario):
    como(cur, cenario.publico2)
    cur.execute(
        "update public.solicitacoes_certidao set dados_declarados = '{}' where id = %s",
        (cenario.sol_p1_A1_aguardando,),
    )
    assert cur.rowcount == 0
    assert estado(cur, cenario.sol_p1_A1_aguardando)["dados_declarados"] != {}


def test_publico_nao_apaga_solicitacao(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute("delete from public.solicitacoes_certidao where id = %s", (cenario.sol_p1_A1_aguardando,))
    assert cur.rowcount == 0


# ---------------------------------------------------------------------------
# paroquial
# ---------------------------------------------------------------------------


def test_paroquial_le_so_a_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    assert ids_visiveis(cur, "solicitacoes_certidao") == {cenario.sol_p1_A1_aguardando, cenario.sol_p1_A1_analise}

    como(cur, cenario.paroquial_B1)
    assert ids_visiveis(cur, "solicitacoes_certidao") == {cenario.sol_p2_B1_analise}


def test_paroquial_rejeita_com_motivo_e_revisao_e_preenchida(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute(
        "update public.solicitacoes_certidao "
        "set status = 'rejeitado', motivo_rejeicao = 'Dados não conferem', revisado_por = %s "
        "where id = %s",
        (cenario.publico1.perfil_id, cenario.sol_p1_A1_analise),  # revisado_por forjado deve ser ignorado
    )
    assert cur.rowcount == 1

    depois = estado(cur, cenario.sol_p1_A1_analise)
    assert depois["status"] == "rejeitado"
    assert depois["motivo_rejeicao"] == "Dados não conferem"
    assert depois["revisado_por"] == cenario.paroquial_A1.perfil_id
    assert depois["revisado_em"] is not None


@pytest.mark.parametrize("motivo", [None, "", "   "])
def test_paroquial_nao_rejeita_sem_motivo(cur, cenario, motivo):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur, errors.CheckViolation):
        cur.execute(
            "update public.solicitacoes_certidao set status = 'rejeitado', motivo_rejeicao = %s where id = %s",
            (motivo, cenario.sol_p1_A1_analise),
        )
    assert estado(cur, cenario.sol_p1_A1_analise)["status"] == "em_analise"


def test_paroquial_nao_aprova_diretamente(cur, cenario):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur):
        cur.execute(
            "update public.solicitacoes_certidao set status = 'aprovado' where id = %s",
            (cenario.sol_p1_A1_analise,),
        )
    assert estado(cur, cenario.sol_p1_A1_analise)["status"] == "em_analise"


def test_paroquial_nao_vincula_registro(cur, cenario):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur):
        cur.execute(
            "update public.solicitacoes_certidao set registro_vinculado_id = %s where id = %s",
            (cenario.reg_A1, cenario.sol_p1_A1_analise),
        )
    assert estado(cur, cenario.sol_p1_A1_analise)["registro_vinculado_id"] is None


def test_paroquial_nao_vincula_registro_junto_com_rejeicao(cur, cenario):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur):
        cur.execute(
            "update public.solicitacoes_certidao "
            "set status = 'rejeitado', motivo_rejeicao = 'Motivo', registro_vinculado_id = %s where id = %s",
            (cenario.reg_A1, cenario.sol_p1_A1_analise),
        )
    depois = estado(cur, cenario.sol_p1_A1_analise)
    assert depois["status"] == "em_analise"
    assert depois["registro_vinculado_id"] is None


def test_paroquial_nao_rejeita_solicitacao_aguardando_pagamento(cur, cenario):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur):
        cur.execute(
            "update public.solicitacoes_certidao set status = 'rejeitado', motivo_rejeicao = 'Motivo' where id = %s",
            (cenario.sol_p1_A1_aguardando,),
        )
    assert estado(cur, cenario.sol_p1_A1_aguardando)["status"] == "aguardando_pagamento"


@pytest.mark.parametrize("solicitacao", ["sol_p2_A2_analise", "sol_p2_B1_analise"])
def test_paroquial_nao_mexe_em_outra_paroquia(cur, cenario, solicitacao):
    solicitacao_id = getattr(cenario, solicitacao)
    como(cur, cenario.paroquial_A1)
    cur.execute(
        "update public.solicitacoes_certidao set status = 'rejeitado', motivo_rejeicao = 'Invasor' where id = %s",
        (solicitacao_id,),
    )
    assert cur.rowcount == 0
    cur.execute("delete from public.solicitacoes_certidao where id = %s", (solicitacao_id,))
    assert cur.rowcount == 0

    depois = estado(cur, solicitacao_id)
    assert depois["status"] == "em_analise"
    assert depois["motivo_rejeicao"] is None


# ---------------------------------------------------------------------------
# diocesano
# ---------------------------------------------------------------------------


def test_diocesano_le_so_a_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    assert ids_visiveis(cur, "solicitacoes_certidao") == {
        cenario.sol_p1_A1_aguardando,
        cenario.sol_p1_A1_analise,
        cenario.sol_p2_A2_analise,
    }

    como(cur, cenario.diocesano_Beta)
    assert ids_visiveis(cur, "solicitacoes_certidao") == {cenario.sol_p2_B1_analise}


def test_diocesano_nao_edita(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    cur.execute(
        "update public.solicitacoes_certidao set status = 'rejeitado', motivo_rejeicao = 'Diocese' where id = %s",
        (cenario.sol_p1_A1_analise,),
    )
    assert cur.rowcount == 0
    cur.execute("delete from public.solicitacoes_certidao where id = %s", (cenario.sol_p2_A2_analise,))
    assert cur.rowcount == 0

    assert estado(cur, cenario.sol_p1_A1_analise)["status"] == "em_analise"
    assert valor(cur, "select count(*) from public.solicitacoes_certidao where id = %s", (cenario.sol_p2_A2_analise,)) == 1
