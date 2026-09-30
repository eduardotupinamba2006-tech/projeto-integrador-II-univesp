"""RLS: pagamentos, dizimistas e doacoes."""

import pytest

from conftest import como, como_postgres, espera_erro, ids_visiveis, valor

pytestmark = pytest.mark.rls

# Paróquia usada por cada usuário nas tentativas de escrita.
PAROQUIA_DE = {
    "publico1": "a1",
    "paroquial_A1": "a1",
    "diocesano_Alfa": "a1",
}


# ---------------------------------------------------------------------------
# pagamentos
# ---------------------------------------------------------------------------


def test_pagamentos_publico_le_so_os_proprios(cur, cenario):
    como(cur, cenario.publico1)
    assert ids_visiveis(cur, "pagamentos") == {cenario.pag_p1_A1_dizimo, cenario.pag_p1_A1_taxa}

    como(cur, cenario.publico2)
    assert ids_visiveis(cur, "pagamentos") == {cenario.pag_p2_A2_dizimo, cenario.pag_p2_B1_dizimo}


def test_pagamentos_paroquial_le_so_a_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    assert ids_visiveis(cur, "pagamentos") == {cenario.pag_p1_A1_dizimo, cenario.pag_p1_A1_taxa}

    como(cur, cenario.paroquial_B1)
    assert ids_visiveis(cur, "pagamentos") == {cenario.pag_p2_B1_dizimo}


def test_pagamentos_diocesano_le_so_a_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    assert ids_visiveis(cur, "pagamentos") == {
        cenario.pag_p1_A1_dizimo,
        cenario.pag_p1_A1_taxa,
        cenario.pag_p2_A2_dizimo,
    }

    como(cur, cenario.diocesano_Beta)
    assert ids_visiveis(cur, "pagamentos") == {cenario.pag_p2_B1_dizimo}


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1", "diocesano_Alfa"])
def test_pagamentos_ninguem_insere(cur, cenario, quem):
    usuario = getattr(cenario, quem)
    como(cur, usuario)
    with espera_erro(cur):
        cur.execute(
            "insert into public.pagamentos (tipo, paroquia_id, usuario_id, valor, status) "
            "values ('dizimo', %s, %s, 10, 'pago')",
            (getattr(cenario, PAROQUIA_DE[quem]), usuario.perfil_id),
        )


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1", "diocesano_Alfa"])
def test_pagamentos_ninguem_marca_como_pago(cur, cenario, quem):
    # pag_p1_A1_taxa é visível aos três (dono, paroquial da A1, diocesano da Alfa).
    como(cur, getattr(cenario, quem))
    assert cenario.pag_p1_A1_taxa in ids_visiveis(cur, "pagamentos")
    cur.execute("update public.pagamentos set status = 'pago' where id = %s", (cenario.pag_p1_A1_taxa,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select status from public.pagamentos where id = %s", (cenario.pag_p1_A1_taxa,)) == "pendente"


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1", "diocesano_Alfa"])
def test_pagamentos_ninguem_apaga(cur, cenario, quem):
    como(cur, getattr(cenario, quem))
    cur.execute("delete from public.pagamentos where id = %s", (cenario.pag_p1_A1_taxa,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select count(*) from public.pagamentos where id = %s", (cenario.pag_p1_A1_taxa,)) == 1


# ---------------------------------------------------------------------------
# dizimistas
# ---------------------------------------------------------------------------


def test_dizimistas_publico_cadastra_a_si_mesmo(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute(
        "insert into public.dizimistas (perfil_id, paroquia_id) values (%s, %s) returning perfil_id",
        (cenario.publico1.perfil_id, cenario.a2),
    )
    assert cur.fetchone()[0] == cenario.publico1.perfil_id


def test_dizimistas_publico_nao_cadastra_outro(cur, cenario):
    como(cur, cenario.publico1)
    with espera_erro(cur):
        cur.execute(
            "insert into public.dizimistas (perfil_id, paroquia_id) values (%s, %s)",
            (cenario.publico2.perfil_id, cenario.a1),
        )


def test_dizimistas_publico_le_so_o_proprio(cur, cenario):
    como(cur, cenario.publico1)
    assert ids_visiveis(cur, "dizimistas") == {cenario.diz_p1_A1}

    como(cur, cenario.publico2)
    assert ids_visiveis(cur, "dizimistas") == {cenario.diz_p2_A2, cenario.diz_p2_B1}


def test_dizimistas_publico_nao_troca_perfil_id(cur, cenario):
    como(cur, cenario.publico1)
    with espera_erro(cur):
        cur.execute(
            "update public.dizimistas set perfil_id = %s where id = %s",
            (cenario.publico2.perfil_id, cenario.diz_p1_A1),
        )

    como_postgres(cur)
    perfil = valor(cur, "select perfil_id from public.dizimistas where id = %s", (cenario.diz_p1_A1,))
    assert perfil == cenario.publico1.perfil_id


def test_dizimistas_publico_troca_de_paroquia(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute("update public.dizimistas set paroquia_id = %s where id = %s", (cenario.a2, cenario.diz_p1_A1))
    assert cur.rowcount == 1


def test_dizimistas_publico_nao_edita_de_outro(cur, cenario):
    como(cur, cenario.publico1)
    cur.execute("update public.dizimistas set paroquia_id = %s where id = %s", (cenario.a1, cenario.diz_p2_A2))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select paroquia_id from public.dizimistas where id = %s", (cenario.diz_p2_A2,)) == cenario.a2


def test_dizimistas_paroquial_le_so_a_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    assert ids_visiveis(cur, "dizimistas") == {cenario.diz_p1_A1}

    como(cur, cenario.paroquial_A2)
    assert ids_visiveis(cur, "dizimistas") == {cenario.diz_p2_A2}


def test_dizimistas_diocesano_le_so_a_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    assert ids_visiveis(cur, "dizimistas") == {cenario.diz_p1_A1, cenario.diz_p2_A2}

    como(cur, cenario.diocesano_Beta)
    assert ids_visiveis(cur, "dizimistas") == {cenario.diz_p2_B1}


@pytest.mark.parametrize("quem", ["paroquial_A1", "diocesano_Alfa"])
def test_dizimistas_paroquial_diocesano_nao_escrevem(cur, cenario, quem):
    como(cur, getattr(cenario, quem))
    with espera_erro(cur):
        cur.execute(
            "insert into public.dizimistas (perfil_id, paroquia_id) values (%s, %s)",
            (cenario.publico1.perfil_id, cenario.a1),
        )

    cur.execute("update public.dizimistas set paroquia_id = %s where id = %s", (cenario.a2, cenario.diz_p1_A1))
    assert cur.rowcount == 0
    cur.execute("delete from public.dizimistas where id = %s", (cenario.diz_p1_A1,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select paroquia_id from public.dizimistas where id = %s", (cenario.diz_p1_A1,)) == cenario.a1


def test_dizimistas_dono_nao_apaga(cur, cenario):
    # Não há política de DELETE: nem o próprio dizimista apaga o cadastro.
    como(cur, cenario.publico1)
    cur.execute("delete from public.dizimistas where id = %s", (cenario.diz_p1_A1,))
    assert cur.rowcount == 0


# ---------------------------------------------------------------------------
# doacoes
# ---------------------------------------------------------------------------


def test_doacoes_publico_le_so_as_dos_proprios_dizimistas(cur, cenario):
    como(cur, cenario.publico1)
    assert ids_visiveis(cur, "doacoes") == {cenario.doa_p1_A1}

    como(cur, cenario.publico2)
    assert ids_visiveis(cur, "doacoes") == {cenario.doa_p2_A2, cenario.doa_p2_B1}


def test_doacoes_paroquial_le_so_a_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    assert ids_visiveis(cur, "doacoes") == {cenario.doa_p1_A1}

    como(cur, cenario.paroquial_B1)
    assert ids_visiveis(cur, "doacoes") == {cenario.doa_p2_B1}


def test_doacoes_diocesano_le_so_a_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    assert ids_visiveis(cur, "doacoes") == {cenario.doa_p1_A1, cenario.doa_p2_A2}

    como(cur, cenario.diocesano_Beta)
    assert ids_visiveis(cur, "doacoes") == {cenario.doa_p2_B1}


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1", "diocesano_Alfa"])
def test_doacoes_ninguem_insere(cur, cenario, quem):
    como(cur, getattr(cenario, quem))
    with espera_erro(cur):
        cur.execute(
            "insert into public.doacoes (dizimista_id, paroquia_id, pagamento_id) values (%s, %s, %s)",
            (cenario.diz_p1_A1, cenario.a1, cenario.pag_p1_A1_taxa),
        )


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1", "diocesano_Alfa"])
def test_doacoes_ninguem_edita_nem_apaga(cur, cenario, quem):
    como(cur, getattr(cenario, quem))
    cur.execute("update public.doacoes set pagamento_id = %s where id = %s", (cenario.pag_p1_A1_taxa, cenario.doa_p1_A1))
    assert cur.rowcount == 0
    cur.execute("delete from public.doacoes where id = %s", (cenario.doa_p1_A1,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select pagamento_id from public.doacoes where id = %s", (cenario.doa_p1_A1,)) == cenario.pag_p1_A1_dizimo
