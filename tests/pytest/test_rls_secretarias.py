"""Vínculo de secretarias de paróquia pelo painel diocesano (funções security definer)."""

import pytest
from psycopg import errors

from conftest import como, como_anon, como_postgres, espera_erro, valor

pytestmark = pytest.mark.rls


def email_de(cur, usuario):
    como_postgres(cur)
    return valor(cur, "select email from auth.users where id = %s", (usuario.auth_id,))


def papel_e_paroquia(cur, usuario):
    como_postgres(cur)
    cur.execute("select papel, paroquia_id from public.perfis where id = %s", (usuario.perfil_id,))
    return cur.fetchone()


def test_diocesano_vincula_conta_publica_a_paroquia_da_diocese(cur, cenario):
    email = email_de(cur, cenario.publico1)
    como(cur, cenario.diocesano_Alfa)
    cur.execute("select public.vincular_secretaria(%s, %s)", (email.upper(), cenario.a2))
    assert papel_e_paroquia(cur, cenario.publico1) == ("paroquial", cenario.a2)


def test_diocesano_lista_so_secretarias_da_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    cur.execute("select perfil_id, paroquia_id from public.secretarias_da_diocese()")
    assert set(cur.fetchall()) == {
        (cenario.paroquial_A1.perfil_id, cenario.a1),
        (cenario.paroquial_A2.perfil_id, cenario.a2),
    }


@pytest.mark.parametrize("quem", ["publico1", "paroquial_A1"])
def test_quem_nao_e_diocesano_nao_lista_nem_vincula(cur, cenario, quem):
    email = email_de(cur, cenario.publico2)
    como(cur, getattr(cenario, quem))
    cur.execute("select count(*) from public.secretarias_da_diocese()")
    assert cur.fetchone()[0] == 0
    with espera_erro(cur):
        cur.execute("select public.vincular_secretaria(%s, %s)", (email, cenario.a1))
    assert papel_e_paroquia(cur, cenario.publico2) == ("publico", None)


def test_anonimo_nao_executa_as_funcoes(cur, cenario):
    como_anon(cur)
    with espera_erro(cur):
        cur.execute("select public.secretarias_da_diocese()")
    with espera_erro(cur):
        cur.execute("select public.vincular_secretaria('x@teste.invalid', %s)", (cenario.a1,))


def test_diocesano_nao_vincula_em_paroquia_de_outra_diocese(cur, cenario):
    email = email_de(cur, cenario.publico1)
    como(cur, cenario.diocesano_Alfa)
    with espera_erro(cur):
        cur.execute("select public.vincular_secretaria(%s, %s)", (email, cenario.b1))
    assert papel_e_paroquia(cur, cenario.publico1) == ("publico", None)


def test_nao_rouba_secretaria_de_outra_diocese(cur, cenario):
    email = email_de(cur, cenario.paroquial_B1)
    como(cur, cenario.diocesano_Alfa)
    with espera_erro(cur):
        cur.execute("select public.vincular_secretaria(%s, %s)", (email, cenario.a1))
    assert papel_e_paroquia(cur, cenario.paroquial_B1) == ("paroquial", cenario.b1)


def test_nao_transforma_diocese_em_secretaria(cur, cenario):
    email = email_de(cur, cenario.diocesano_Beta)
    como(cur, cenario.diocesano_Alfa)
    with espera_erro(cur):
        cur.execute("select public.vincular_secretaria(%s, %s)", (email, cenario.a1))


def test_email_sem_conta(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    with espera_erro(cur, errors.NoDataFound):
        cur.execute("select public.vincular_secretaria('ninguem@teste.invalid', %s)", (cenario.a1,))


def test_diocesano_desvincula_secretaria_da_propria_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    cur.execute("select public.desvincular_secretaria(%s)", (cenario.paroquial_A1.perfil_id,))
    assert papel_e_paroquia(cur, cenario.paroquial_A1) == ("publico", None)


def test_diocesano_nao_desvincula_secretaria_de_outra_diocese(cur, cenario):
    como(cur, cenario.diocesano_Alfa)
    with espera_erro(cur):
        cur.execute("select public.desvincular_secretaria(%s)", (cenario.paroquial_B1.perfil_id,))
    assert papel_e_paroquia(cur, cenario.paroquial_B1) == ("paroquial", cenario.b1)
