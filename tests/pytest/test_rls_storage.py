"""RLS do bucket de certidões e gatilhos de email sem Vault configurado."""

import pytest

from conftest import como, como_anon, como_postgres, espera_erro, valor

pytestmark = pytest.mark.rls


def _objeto(cur, dono, nome_arquivo):
    return valor(
        cur,
        "insert into storage.objects (bucket_id, name) values ('certidoes', %s) returning name",
        ("{}/{}".format(dono.perfil_id, nome_arquivo),),
    )


def _nomes_visiveis(cur):
    cur.execute("select name from storage.objects where bucket_id = 'certidoes'")
    return {linha[0] for linha in cur.fetchall()}


def test_bucket_de_certidoes_e_privado(cur):
    assert valor(cur, "select public from storage.buckets where id = 'certidoes'") is False


def test_solicitante_le_so_as_proprias_certidoes(cur, cenario):
    minha = _objeto(cur, cenario.publico1, "a.pdf")
    alheia = _objeto(cur, cenario.publico2, "b.pdf")

    como(cur, cenario.publico1)
    assert _nomes_visiveis(cur) == {minha}

    como(cur, cenario.publico2)
    assert _nomes_visiveis(cur) == {alheia}


@pytest.mark.parametrize("quem", ["paroquial_A1", "diocesano_Alfa"])
def test_paroquia_e_diocese_nao_leem_pdfs_de_solicitantes(cur, cenario, quem):
    _objeto(cur, cenario.publico1, "a.pdf")
    como(cur, getattr(cenario, quem))
    assert _nomes_visiveis(cur) == set()


def test_anon_nao_le_certidoes(cur, cenario):
    _objeto(cur, cenario.publico1, "a.pdf")
    como_anon(cur)
    assert _nomes_visiveis(cur) == set()


def test_usuario_nao_grava_no_bucket(cur, cenario):
    como(cur, cenario.publico1)
    with espera_erro(cur):
        cur.execute(
            "insert into storage.objects (bucket_id, name) values ('certidoes', %s)",
            ("{}/forjada.pdf".format(cenario.publico1.perfil_id),),
        )


def test_gatilhos_de_email_nao_quebram_sem_vault(cur, cenario):
    """Sem os segredos no Vault (como no CI), os gatilhos não chamam nada e a escrita segue."""
    como_postgres(cur)
    cur.execute(
        "update public.pagamentos set status = 'pago' where id = %s returning status",
        (cenario.pag_p1_A1_taxa,),
    )
    assert cur.fetchone()[0] == "pago"
    assert valor(cur, "select count(*) from net.http_request_queue") == 0
