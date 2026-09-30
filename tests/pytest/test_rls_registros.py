"""RLS: registros_sacramentais."""

import pytest

from conftest import como, como_postgres, espera_erro, ids_visiveis, valor

pytestmark = pytest.mark.rls

SQL_INSERIR = (
    "insert into public.registros_sacramentais (paroquia_id, tipo, nome_pessoa, data_sacramento) "
    "values (%s, 'batismo', 'Fulano Fictício Novo', '2020-05-05')"
)


def nome_do_registro(cur, registro_id):
    como_postgres(cur)
    return valor(cur, "select nome_pessoa from public.registros_sacramentais where id = %s", (registro_id,))


# --- paroquial --------------------------------------------------------------


def test_paroquial_le_so_a_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    assert ids_visiveis(cur, "registros_sacramentais") == {cenario.reg_A1, cenario.reg_A1_b}


def test_paroquial_insere_na_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute(SQL_INSERIR + " returning paroquia_id", (cenario.a1,))
    assert cur.fetchone()[0] == cenario.a1


@pytest.mark.parametrize("paroquia", ["a2", "b1"])
def test_paroquial_nao_insere_em_outra_paroquia(cur, cenario, paroquia):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur):
        cur.execute(SQL_INSERIR, (getattr(cenario, paroquia),))


def test_criado_por_e_preenchido_pelo_servidor(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute(
        "insert into public.registros_sacramentais "
        "(paroquia_id, tipo, nome_pessoa, data_sacramento, criado_por, criado_em) "
        "values (%s, 'batismo', 'Fulano Fictício Novo', '2020-05-05', %s, '1999-01-01') "
        "returning criado_por, criado_em",
        (cenario.a1, cenario.publico1.perfil_id),
    )
    criado_por, criado_em = cur.fetchone()
    assert criado_por == cenario.paroquial_A1.perfil_id
    assert criado_em.year != 1999


def test_paroquial_nao_troca_criado_por_ao_editar(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute(
        "update public.registros_sacramentais set criado_por = %s where id = %s",
        (cenario.publico1.perfil_id, cenario.reg_A1),
    )
    assert cur.rowcount == 1

    como_postgres(cur)
    criado_por = valor(cur, "select criado_por from public.registros_sacramentais where id = %s", (cenario.reg_A1,))
    assert criado_por == cenario.paroquial_A1.perfil_id


def test_paroquial_edita_na_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute("update public.registros_sacramentais set nome_pessoa = 'Editado' where id = %s", (cenario.reg_A1,))
    assert cur.rowcount == 1
    assert nome_do_registro(cur, cenario.reg_A1) == "Editado"


@pytest.mark.parametrize("registro", ["reg_A2", "reg_B1"])
def test_paroquial_nao_edita_outra_paroquia(cur, cenario, registro):
    registro_id = getattr(cenario, registro)
    como(cur, cenario.paroquial_A1)
    cur.execute("update public.registros_sacramentais set nome_pessoa = 'Invasor' where id = %s", (registro_id,))
    assert cur.rowcount == 0
    assert nome_do_registro(cur, registro_id) != "Invasor"


def test_paroquial_nao_move_registro_para_outra_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    with espera_erro(cur):
        cur.execute(
            "update public.registros_sacramentais set paroquia_id = %s where id = %s",
            (cenario.a2, cenario.reg_A1),
        )

    como_postgres(cur)
    assert valor(cur, "select paroquia_id from public.registros_sacramentais where id = %s", (cenario.reg_A1,)) == cenario.a1


def test_paroquial_apaga_na_propria_paroquia(cur, cenario):
    como(cur, cenario.paroquial_A1)
    cur.execute("delete from public.registros_sacramentais where id = %s", (cenario.reg_A1_b,))
    assert cur.rowcount == 1

    como_postgres(cur)
    assert valor(cur, "select count(*) from public.registros_sacramentais where id = %s", (cenario.reg_A1_b,)) == 0


@pytest.mark.parametrize("registro", ["reg_A2", "reg_B1"])
def test_paroquial_nao_apaga_outra_paroquia(cur, cenario, registro):
    registro_id = getattr(cenario, registro)
    como(cur, cenario.paroquial_A1)
    cur.execute("delete from public.registros_sacramentais where id = %s", (registro_id,))
    assert cur.rowcount == 0

    como_postgres(cur)
    assert valor(cur, "select count(*) from public.registros_sacramentais where id = %s", (registro_id,)) == 1


# --- diocesano --------------------------------------------------------------


def test_diocesano_le_so_a_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    assert ids_visiveis(cur, "registros_sacramentais") == {cenario.reg_A1, cenario.reg_A1_b, cenario.reg_A2}

    como(cur, cenario.diocesano_Beta)
    assert ids_visiveis(cur, "registros_sacramentais") == {cenario.reg_B1}


def test_diocesano_nao_insere(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    with espera_erro(cur):
        cur.execute(SQL_INSERIR, (cenario.a1,))


def test_diocesano_nao_edita_nem_apaga(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    cur.execute("update public.registros_sacramentais set nome_pessoa = 'Invasor' where id = %s", (cenario.reg_A1,))
    assert cur.rowcount == 0
    cur.execute("delete from public.registros_sacramentais where id = %s", (cenario.reg_A2,))
    assert cur.rowcount == 0

    assert nome_do_registro(cur, cenario.reg_A1) != "Invasor"
    assert valor(cur, "select count(*) from public.registros_sacramentais where id = %s", (cenario.reg_A2,)) == 1


# --- público ----------------------------------------------------------------


@pytest.mark.parametrize("quem", ["publico1", "publico2"])
def test_publico_nao_le_registros(cur, cenario, quem):
    como(cur, getattr(cenario, quem))
    assert ids_visiveis(cur, "registros_sacramentais") == set()


def test_publico_nao_insere_edita_nem_apaga(cur, cenario):
    como(cur, cenario.publico1)
    with espera_erro(cur):
        cur.execute(SQL_INSERIR, (cenario.a1,))
    cur.execute("update public.registros_sacramentais set nome_pessoa = 'Invasor' where id = %s", (cenario.reg_A1,))
    assert cur.rowcount == 0
    cur.execute("delete from public.registros_sacramentais where id = %s", (cenario.reg_A1,))
    assert cur.rowcount == 0
    assert nome_do_registro(cur, cenario.reg_A1) == "Beltrano Fictício A1"
