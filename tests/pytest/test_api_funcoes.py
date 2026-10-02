"""Testes das funções serverless (api/*.py) com Supabase, Mercado Pago e Brevo falsos."""

import hashlib
import hmac
import os
import sys
from datetime import date
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

import cobranca_pix  # noqa: E402
import enviar_email  # noqa: E402
import pdf  # noqa: E402
import validar_qrcode  # noqa: E402
import webhook_pagamento  # noqa: E402
from _lib import brevo, certidao_pdf, emails, mercadopago, token_qr  # noqa: E402

from falsos import MercadoPagoFalso, BrevoFalso, SupabaseFalso  # noqa: E402

SEGREDO_QR = "segredo-qr-de-teste"


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://site.teste")
    monkeypatch.setenv("QR_SECRET", SEGREDO_QR)
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.teste")


@pytest.fixture
def sb(monkeypatch, ambiente):
    falso = SupabaseFalso()
    for modulo in (cobranca_pix, webhook_pagamento, pdf, validar_qrcode, enviar_email):
        monkeypatch.setattr(modulo, "supabase", falso)
    return falso


@pytest.fixture
def mp(monkeypatch):
    falso = MercadoPagoFalso()
    for nome in ("criar_pix", "consultar"):
        monkeypatch.setattr(mercadopago, nome, getattr(falso, nome))
    return falso


@pytest.fixture
def dados(sb):
    """Cenário sintético mínimo: uma diocese, duas paróquias, fiel e secretaria paroquial."""
    diocese = sb.semear("dioceses", {"nome": "Diocese Alfa (fictícia)", "uf": "SP"})
    p1 = sb.semear("paroquias", {"diocese_id": diocese["id"], "nome": "Paróquia São Exemplo", "endereco": "Rua Fictícia, 1"})
    p2 = sb.semear("paroquias", {"diocese_id": diocese["id"], "nome": "Paróquia Santa Amostra", "endereco": "Rua Fictícia, 2"})
    fiel = sb.semear("perfis", {"nome": "Fiel Sintético", "papel": "publico", "paroquia_id": None})
    outro = sb.semear("perfis", {"nome": "Outro Fiel", "papel": "publico", "paroquia_id": None})
    secretaria = sb.semear("perfis", {"nome": "Secretaria", "papel": "paroquial", "paroquia_id": p1["id"]})
    registro = sb.semear("registros_sacramentais", {
        "paroquia_id": p1["id"], "tipo": "batismo", "nome_pessoa": "Nome Oficial Do Livro",
        "data_sacramento": "1995-03-12", "livro": "12", "folha": "34", "numero": "567",
        "celebrante": "Pe. Fictício", "padrinhos": "Padrinho e Madrinha",
    })
    sol = sb.semear("solicitacoes_certidao", {
        "solicitante_id": fiel["id"], "paroquia_id": p1["id"], "tipo": "batismo",
        "dados_declarados": {"nome_pessoa": "Nome Digitado Pelo Usuario"},
        "status": "aguardando_pagamento", "pagamento_id": None, "registro_vinculado_id": None,
    })
    sb.emails[fiel["id"]] = ("fiel@teste.local", "Fiel Sintético")
    return {"diocese": diocese, "p1": p1, "p2": p2, "fiel": fiel, "outro": outro,
            "secretaria": secretaria, "registro": registro, "sol": sol}


# ---------------------------------------------------------------------------
# Token do QR Code
# ---------------------------------------------------------------------------

class TestTokenQr:
    ID = "f0000000-0000-0000-0000-000000000001"

    def test_token_gerado_e_verificado(self):
        assert token_qr.verificar(token_qr.gerar(self.ID, "s"), "s") == self.ID

    def test_token_adulterado_e_recusado(self):
        token = token_qr.gerar(self.ID, "s")
        outro_id = "f0000000-0000-0000-0000-000000000002"
        assert token_qr.verificar(outro_id + "." + token.split(".")[1], "s") is None
        assert token_qr.verificar(token[:-2] + "xx", "s") is None

    def test_segredo_diferente_e_recusado(self):
        assert token_qr.verificar(token_qr.gerar(self.ID, "s"), "outro") is None

    @pytest.mark.parametrize("token", ["", "sem-ponto", "a.b.c", "nao-e-uuid.abc", None])
    def test_token_malformado_e_recusado(self, token):
        assert token_qr.verificar(token, "s") is None


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def test_data_por_extenso():
    assert certidao_pdf.data_por_extenso("1995-03-12") == "12 de março de 1995"
    assert certidao_pdf.data_por_extenso(date(2026, 12, 1)) == "1 de dezembro de 2026"


@pytest.mark.parametrize("tipo", sorted(certidao_pdf.TITULOS))
def test_pdf_gerado_para_cada_sacramento(dados, tipo):
    registro = dict(dados["registro"], tipo=tipo)
    conteudo = certidao_pdf.gerar_pdf(registro, dados["p1"], dados["diocese"], "https://site.teste/validar.html?c=x")
    assert conteudo.startswith(b"%PDF")
    assert len(conteudo) > 1000


# ---------------------------------------------------------------------------
# Cobrança Pix
# ---------------------------------------------------------------------------

class TestCobrancaPix:
    def test_taxa_de_certidao_usa_valor_fixo_do_servidor(self, dados, sb, mp):
        status, resp = cobranca_pix.processar(
            dados["fiel"], "fiel@teste.local",
            {"tipo": "taxa_certidao", "solicitacao_id": dados["sol"]["id"], "valor": "0.01"},
        )
        assert status == 200
        assert Decimal(resp["valor"]) == Decimal("30.00")
        assert mp.cobrancas[0]["valor"] == "30.00"
        pagamento = sb.selecionar_um("pagamentos", {"id": "eq." + resp["pagamento_id"]})
        assert pagamento["tipo"] == "taxa_certidao"
        assert pagamento["status"] == "pendente"
        assert pagamento["id_transacao_externa"] == "1001"
        sol = sb.selecionar_um("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]})
        assert sol["pagamento_id"] == pagamento["id"]

    def test_nao_cobra_solicitacao_de_outro_usuario(self, dados, sb, mp):
        status, _ = cobranca_pix.processar(
            dados["outro"], "x@teste.local", {"tipo": "taxa_certidao", "solicitacao_id": dados["sol"]["id"]}
        )
        assert status == 404
        assert mp.cobrancas == []

    def test_nao_cobra_solicitacao_ja_paga(self, dados, sb, mp):
        sb.atualizar("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]}, {"status": "em_analise"})
        status, _ = cobranca_pix.processar(
            dados["fiel"], "f@teste.local", {"tipo": "taxa_certidao", "solicitacao_id": dados["sol"]["id"]}
        )
        assert status == 409

    def test_segunda_chamada_reaproveita_a_cobranca(self, dados, sb, mp):
        corpo = {"tipo": "taxa_certidao", "solicitacao_id": dados["sol"]["id"]}
        _, primeira = cobranca_pix.processar(dados["fiel"], "f@teste.local", corpo)
        mp.pagamentos["1001"] = {"qr_code": "000201PIX"}
        _, segunda = cobranca_pix.processar(dados["fiel"], "f@teste.local", corpo)
        assert segunda["pagamento_id"] == primeira["pagamento_id"]
        assert len(mp.cobrancas) == 1
        assert len(sb.tabelas["pagamentos"]) == 1

    def test_dizimo_cobra_valor_integral_sem_taxa(self, dados, sb, mp):
        status, resp = cobranca_pix.processar(
            dados["fiel"], "f@teste.local", {"tipo": "dizimo", "paroquia_id": dados["p2"]["id"], "valor": "123.45"}
        )
        assert status == 200
        assert resp["valor"] == "123.45"
        assert mp.cobrancas[0]["valor"] == "123.45"
        pagamento = sb.selecionar_um("pagamentos", {"id": "eq." + resp["pagamento_id"]})
        assert pagamento["tipo"] == "dizimo"
        assert pagamento["paroquia_id"] == dados["p2"]["id"]

    def test_pagador_e_o_dono_da_conta(self, dados, sb, mp, monkeypatch):
        monkeypatch.delenv("MP_EMAIL_PAGADOR_TESTE", raising=False)
        cobranca_pix.processar(dados["fiel"], "f@teste.local", {"tipo": "dizimo", "paroquia_id": dados["p1"]["id"], "valor": "10"})
        assert mp.cobrancas[0]["pagador"] == {"email": "f@teste.local"}

    def test_sandbox_usa_comprador_de_teste_aprovado_automaticamente(self, dados, sb, mp, monkeypatch):
        monkeypatch.setenv("MP_EMAIL_PAGADOR_TESTE", "test_user_1@testuser.com")
        cobranca_pix.processar(dados["fiel"], "f@teste.local", {"tipo": "dizimo", "paroquia_id": dados["p1"]["id"], "valor": "10"})
        assert mp.cobrancas[0]["pagador"] == {"email": "test_user_1@testuser.com", "first_name": "APRO"}

    def test_email_de_teste_com_espacos_e_aspas_e_limpo(self, dados, sb, mp, monkeypatch):
        monkeypatch.setenv("MP_EMAIL_PAGADOR_TESTE", ' "test_user_1@testuser.com" ')
        cobranca_pix.processar(dados["fiel"], "f@teste.local", {"tipo": "dizimo", "paroquia_id": dados["p1"]["id"], "valor": "10"})
        assert mp.cobrancas[0]["pagador"]["email"] == "test_user_1@testuser.com"

    @pytest.mark.parametrize("valor", ["0", "0.99", "-10", "abc", "10.001", "100000.01", "NaN", None])
    def test_dizimo_com_valor_invalido(self, dados, sb, mp, valor):
        status, _ = cobranca_pix.processar(
            dados["fiel"], "f@teste.local", {"tipo": "dizimo", "paroquia_id": dados["p1"]["id"], "valor": valor}
        )
        assert status == 400
        assert mp.cobrancas == []

    def test_dizimo_para_paroquia_inexistente(self, dados, sb, mp):
        status, _ = cobranca_pix.processar(
            dados["fiel"], "f@teste.local",
            {"tipo": "dizimo", "paroquia_id": "a0000000-0000-0000-0000-000000000999", "valor": "10"},
        )
        assert status == 404

    def test_conferir_confirma_pagamento_aprovado(self, dados, sb, mp):
        _, pix = cobranca_pix.processar(dados["fiel"], "f@teste.local", {"tipo": "taxa_certidao", "solicitacao_id": dados["sol"]["id"]})
        corpo = {"tipo": "conferir", "pagamento_id": pix["pagamento_id"]}
        mp.pagamentos["1001"] = {"status": "action_required", "external_reference": pix["pagamento_id"], "valor": "30.00"}
        assert cobranca_pix.processar(dados["fiel"], "f@teste.local", corpo) == (200, {"status": "pendente"})

        mp.pagamentos["1001"]["status"] = "processed"
        assert cobranca_pix.processar(dados["fiel"], "f@teste.local", corpo) == (200, {"status": "pago"})
        assert sb.selecionar_um("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]})["status"] == "em_analise"

    def test_conferir_pagamento_de_outro_usuario(self, dados, sb, mp):
        _, pix = cobranca_pix.processar(dados["fiel"], "f@teste.local", {"tipo": "dizimo", "paroquia_id": dados["p1"]["id"], "valor": "10"})
        status, _ = cobranca_pix.processar(dados["outro"], "x@teste.local", {"tipo": "conferir", "pagamento_id": pix["pagamento_id"]})
        assert status == 404

    def test_tipo_invalido(self, dados, sb, mp):
        assert cobranca_pix.processar(dados["fiel"], "f@teste.local", {"tipo": "outro"})[0] == 400


# ---------------------------------------------------------------------------
# Webhook de pagamento
# ---------------------------------------------------------------------------

class TestWebhookPagamento:
    def _pagamento(self, sb, dados, tipo, valor="30.00", ext="555"):
        return sb.semear("pagamentos", {
            "tipo": tipo, "paroquia_id": dados["p1"]["id"], "usuario_id": dados["fiel"]["id"],
            "valor": valor, "status": "pendente", "id_transacao_externa": ext,
        })

    def test_taxa_paga_coloca_solicitacao_em_analise(self, dados, sb, mp):
        pag = self._pagamento(sb, dados, "taxa_certidao")
        sb.atualizar("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]}, {"pagamento_id": pag["id"]})
        mp.pagamentos["555"] = {"status": "processed", "external_reference": pag["id"], "valor": "30.0"}

        status, resp = webhook_pagamento.processar_pagamento("555")

        assert (status, resp["status"]) == (200, "pago")
        assert sb.selecionar_um("pagamentos", {"id": "eq." + pag["id"]})["status"] == "pago"
        assert sb.selecionar_um("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]})["status"] == "em_analise"

    def test_dizimo_pago_de_dizimista_gera_doacao(self, dados, sb, mp):
        dizimista = sb.semear("dizimistas", {"perfil_id": dados["fiel"]["id"], "paroquia_id": dados["p1"]["id"]})
        pag = self._pagamento(sb, dados, "dizimo", valor="50.00")
        mp.pagamentos["555"] = {"status": "processed", "external_reference": pag["id"], "valor": "50"}

        webhook_pagamento.processar_pagamento("555")
        webhook_pagamento.processar_pagamento("555")  # notificação repetida

        doacoes = sb.tabelas.get("doacoes", [])
        assert len(doacoes) == 1
        assert doacoes[0]["dizimista_id"] == dizimista["id"]
        assert doacoes[0]["pagamento_id"] == pag["id"]

    def test_dizimo_pago_sem_cadastro_de_dizimista_nao_gera_doacao(self, dados, sb, mp):
        pag = self._pagamento(sb, dados, "dizimo", valor="50.00")
        mp.pagamentos["555"] = {"status": "processed", "external_reference": pag["id"], "valor": "50"}
        webhook_pagamento.processar_pagamento("555")
        assert sb.selecionar_um("pagamentos", {"id": "eq." + pag["id"]})["status"] == "pago"
        assert sb.tabelas.get("doacoes", []) == []

    def test_pagamento_pendente_e_ignorado(self, dados, sb, mp):
        pag = self._pagamento(sb, dados, "dizimo")
        mp.pagamentos["555"] = {"status": "action_required", "external_reference": pag["id"], "valor": "30"}
        status, resp = webhook_pagamento.processar_pagamento("555")
        assert status == 200 and "ignorado" in resp
        assert sb.selecionar_um("pagamentos", {"id": "eq." + pag["id"]})["status"] == "pendente"

    def test_valor_divergente_nao_confirma(self, dados, sb, mp):
        pag = self._pagamento(sb, dados, "taxa_certidao")
        mp.pagamentos["555"] = {"status": "processed", "external_reference": pag["id"], "valor": "0.01"}
        assert webhook_pagamento.processar_pagamento("555")[0] == 409
        assert sb.selecionar_um("pagamentos", {"id": "eq." + pag["id"]})["status"] == "pendente"

    def test_id_externo_de_outro_pagamento_nao_confirma(self, dados, sb, mp):
        pag = self._pagamento(sb, dados, "taxa_certidao", ext="999")
        mp.pagamentos["555"] = {"status": "processed", "external_reference": pag["id"], "valor": "30"}
        assert webhook_pagamento.processar_pagamento("555")[0] == 404

    def test_estorno(self, dados, sb, mp):
        pag = self._pagamento(sb, dados, "dizimo")
        sb.atualizar("pagamentos", {"id": "eq." + pag["id"]}, {"status": "pago"})
        mp.pagamentos["555"] = {"status": "refunded", "external_reference": pag["id"], "valor": "30"}
        webhook_pagamento.processar_pagamento("555")
        assert sb.selecionar_um("pagamentos", {"id": "eq." + pag["id"]})["status"] == "estornado"


class TestClienteMercadoPago:
    ORDER = {
        "id": "ORDTST01", "status": "action_required", "external_reference": "pag-1", "total_amount": "30.00",
        "transactions": {"payments": [{"payment_method": {"id": "pix", "qr_code": "000201PIX", "qr_code_base64": "iVBOR", "ticket_url": "https://mp.teste"}}]},
    }

    def test_cria_order_pix_com_idempotencia(self, monkeypatch):
        chamadas = []
        monkeypatch.setenv("MP_ACCESS_TOKEN", "token-teste")
        monkeypatch.setattr(mercadopago, "requisitar", lambda *a, **k: chamadas.append((a, k)) or self.ORDER)

        pix = mercadopago.criar_pix("pag-1", Decimal("30"), "Taxa", {"email": "f@x.com"})

        (metodo, url), opcoes = chamadas[0]
        assert (metodo, url) == ("POST", "https://api.mercadopago.com/v1/orders")
        assert opcoes["headers"]["X-Idempotency-Key"] == "pag-1"
        corpo = opcoes["json_corpo"]
        assert corpo["total_amount"] == "30.00"
        assert corpo["external_reference"] == "pag-1"
        assert corpo["transactions"]["payments"][0] == {"amount": "30.00", "payment_method": {"id": "pix", "type": "bank_transfer"}}
        assert pix == {"id": "ORDTST01", "status": "action_required", "external_reference": "pag-1", "valor": "30.00",
                       "qr_code": "000201PIX", "qr_code_base64": "iVBOR", "ticket_url": "https://mp.teste"}


    def test_espera_o_qr_code_quando_a_order_nasce_processando(self, monkeypatch):
        processando = dict(self.ORDER, status="processing", transactions={"payments": [{"payment_method": {"id": "pix"}}]})
        respostas = [processando, processando, self.ORDER]
        monkeypatch.setenv("MP_ACCESS_TOKEN", "token-teste")
        monkeypatch.setattr(mercadopago, "requisitar", lambda *a, **k: respostas.pop(0))
        monkeypatch.setattr(mercadopago.time, "sleep", lambda s: None)

        pix = mercadopago.criar_pix("pag-1", "30.00", "Taxa", {"email": "f@x.com"})

        assert pix["qr_code"] == "000201PIX"
        assert respostas == []


    def test_order_inexistente_e_ignorada(self, dados, sb, monkeypatch):
        def consultar(id_externo):
            raise webhook_pagamento.ErroHttp(400, '{"errors":[{"code":"invalid_path_param"}]}')
        monkeypatch.setattr(mercadopago, "consultar", consultar)
        assert webhook_pagamento.processar_pagamento("123456") == (200, {"ignorado": "order inexistente"})


class TestAssinaturaMercadoPago:
    SEGREDO = "segredo-webhook"

    def _assinar(self, data_id, request_id, ts):
        manifesto = "id:{};request-id:{};ts:{};".format(data_id, request_id, ts)
        v1 = hmac.new(self.SEGREDO.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
        return "ts={},v1={}".format(ts, v1)

    def test_assinatura_correta(self):
        cabecalho = self._assinar("123", "req-1", "1700000000")
        assert mercadopago.assinatura_valida(cabecalho, "req-1", "123", self.SEGREDO)

    def test_assinatura_de_outro_id(self):
        cabecalho = self._assinar("123", "req-1", "1700000000")
        assert not mercadopago.assinatura_valida(cabecalho, "req-1", "124", self.SEGREDO)

    @pytest.mark.parametrize("cabecalho", [None, "", "ts=1", "v1=abc", "lixo"])
    def test_cabecalho_ausente_ou_malformado(self, cabecalho):
        assert not mercadopago.assinatura_valida(cabecalho, "req-1", "123", self.SEGREDO)


# ---------------------------------------------------------------------------
# Emissão (PDF) pela paróquia
# ---------------------------------------------------------------------------

class TestEmissaoPdf:
    @pytest.fixture
    def em_analise(self, dados, sb):
        sb.atualizar("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]}, {"status": "em_analise"})
        return {"solicitacao_id": dados["sol"]["id"], "registro_id": dados["registro"]["id"]}

    def test_emite_a_partir_do_registro_oficial(self, dados, sb, em_analise, monkeypatch):
        chamadas = []
        original = pdf.certidao_pdf.gerar_pdf

        def espiao(registro, *args, **kwargs):
            chamadas.append(registro)
            return original(registro, *args, **kwargs)

        monkeypatch.setattr(pdf.certidao_pdf, "gerar_pdf", espiao)
        status, _ = pdf.processar(dados["secretaria"], em_analise)

        assert status == 200
        assert chamadas[0]["nome_pessoa"] == "Nome Oficial Do Livro"
        assert "dados_declarados" not in chamadas[0]
        caminho = "{}/{}.pdf".format(dados["fiel"]["id"], dados["sol"]["id"])
        conteudo, tipo = sb.arquivos[("certidoes", caminho)]
        assert conteudo.startswith(b"%PDF") and tipo == "application/pdf"
        sol = sb.selecionar_um("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]})
        assert sol["status"] == "aprovado"
        assert sol["registro_vinculado_id"] == dados["registro"]["id"]
        assert sol["revisado_por"] == dados["secretaria"]["id"]
        assert sol["pdf_gerado_em"]

    def test_publico_nao_emite(self, dados, sb, em_analise):
        assert pdf.processar(dados["fiel"], em_analise)[0] == 403

    def test_paroquial_de_outra_paroquia_nao_emite(self, dados, sb, em_analise):
        intrusa = dict(dados["secretaria"], paroquia_id=dados["p2"]["id"])
        assert pdf.processar(intrusa, em_analise)[0] == 404
        assert sb.arquivos == {}

    def test_registro_de_outra_paroquia_e_recusado(self, dados, sb, em_analise):
        alheio = sb.semear("registros_sacramentais", dict(dados["registro"], id=None, paroquia_id=dados["p2"]["id"]))
        corpo = dict(em_analise, registro_id=alheio["id"])
        assert pdf.processar(dados["secretaria"], corpo)[0] == 404

    def test_registro_de_outro_sacramento_e_recusado(self, dados, sb, em_analise):
        crisma = sb.semear("registros_sacramentais", dict(dados["registro"], id=None, tipo="crisma"))
        assert pdf.processar(dados["secretaria"], dict(em_analise, registro_id=crisma["id"]))[0] == 409

    def test_solicitacao_nao_paga_nao_e_emitida(self, dados, sb):
        corpo = {"solicitacao_id": dados["sol"]["id"], "registro_id": dados["registro"]["id"]}
        assert pdf.processar(dados["secretaria"], corpo)[0] == 409


# ---------------------------------------------------------------------------
# Validação pública do QR Code
# ---------------------------------------------------------------------------

class TestValidarQrcode:
    def test_certidao_aprovada_e_valida(self, dados, sb):
        sb.atualizar("solicitacoes_certidao", {"id": "eq." + dados["sol"]["id"]}, {
            "status": "aprovado", "registro_vinculado_id": dados["registro"]["id"],
            "pdf_gerado_em": "2026-09-30T12:00:00+00:00",
        })
        resp = validar_qrcode.validar(token_qr.gerar(dados["sol"]["id"], SEGREDO_QR))
        assert resp["valida"] is True
        assert resp["certidao"]["nome_pessoa"] == "Nome Oficial Do Livro"
        assert resp["certidao"]["paroquia"] == "Paróquia São Exemplo"
        assert resp["certidao"]["diocese"] == "Diocese Alfa (fictícia)"

    def test_token_invalido(self, dados, sb):
        assert validar_qrcode.validar(dados["sol"]["id"] + ".assinatura-falsa") == {"valida": False}

    def test_solicitacao_nao_aprovada(self, dados, sb):
        assert validar_qrcode.validar(token_qr.gerar(dados["sol"]["id"], SEGREDO_QR)) == {"valida": False}


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------

def _evento(tabela, operacao, novo, antigo=None):
    return {"table": tabela, "type": operacao, "record": novo, "old_record": antigo}


class TestClassificacaoEmails:
    PAG = {"id": "p", "tipo": "dizimo", "status": "pendente"}

    @pytest.mark.parametrize("evento,esperado", [
        (_evento("pagamentos", "INSERT", {"tipo": "dizimo"}), "pagamento_criado_dizimo"),
        (_evento("pagamentos", "INSERT", {"tipo": "taxa_certidao"}), "pagamento_criado_taxa_certidao"),
        (_evento("pagamentos", "UPDATE", {"tipo": "dizimo", "status": "pago"}, {"status": "pendente"}), "recibo_dizimo"),
        (_evento("pagamentos", "UPDATE", {"tipo": "taxa_certidao", "status": "pago"}, {"status": "pendente"}), "certidao_em_analise"),
        (_evento("solicitacoes_certidao", "UPDATE", {"status": "aprovado"}, {"status": "em_analise"}), "certidao_aprovada"),
        (_evento("solicitacoes_certidao", "UPDATE", {"status": "rejeitado"}, {"status": "em_analise"}), "certidao_rejeitada"),
        (_evento("pagamentos", "UPDATE", {"tipo": "dizimo", "status": "estornado"}, {"status": "pago"}), None),
        (_evento("pagamentos", "UPDATE", {"tipo": "dizimo", "status": "pago"}, {"status": "pago"}), None),
        (_evento("solicitacoes_certidao", "UPDATE", {"status": "em_analise"}, {"status": "aguardando_pagamento"}), None),
        (_evento("solicitacoes_certidao", "INSERT", {"status": "aguardando_pagamento"}), None),
    ])
    def test_classificar(self, evento, esperado):
        assert emails.classificar(evento) == esperado

    def test_motivo_de_rejeicao_e_escapado(self):
        _, html = emails.montar("certidao_rejeitada", {
            "nome": "Fiel", "paroquia": "Paróquia", "sacramento": "batismo", "motivo": "<script>x</script>",
        })
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_formatar_valor(self):
        assert emails.formatar_valor("1234.5") == "R$ 1.234,50"
        assert emails.formatar_valor(30) == "R$ 30,00"


class TestEnvioEmails:
    @pytest.fixture
    def brevo_ok(self, monkeypatch):
        falso = BrevoFalso()
        monkeypatch.setattr(enviar_email, "brevo", falso)
        return falso

    def test_aprovacao_envia_link_do_pdf_e_registra(self, dados, sb, brevo_ok):
        sol = dict(dados["sol"], status="aprovado")
        resp = enviar_email.processar(_evento("solicitacoes_certidao", "UPDATE", sol, dados["sol"]))

        assert resp == {"tipo": "certidao_aprovada", "status_envio": "enviado"}
        assert brevo_ok.enviados[0]["para"] == "fiel@teste.local"
        assert "/object/sign/certidoes/{}/{}.pdf".format(dados["fiel"]["id"], sol["id"]) in brevo_ok.enviados[0]["html"]
        registro = sb.tabelas["emails_enviados"][0]
        assert registro["status_envio"] == "enviado"
        assert registro["referencia_tabela"] == "solicitacoes_certidao"
        assert registro["referencia_id"] == sol["id"]

    def test_recibo_de_dizimo(self, dados, sb, brevo_ok):
        pag = {"id": "pag-1", "tipo": "dizimo", "status": "pago", "valor": "80.00",
               "usuario_id": dados["fiel"]["id"], "paroquia_id": dados["p1"]["id"]}
        enviar_email.processar(_evento("pagamentos", "UPDATE", pag, dict(pag, status="pendente")))
        assert brevo_ok.enviados[0]["assunto"] == "Recibo de doação"
        assert "R$ 80,00" in brevo_ok.enviados[0]["html"]

    def test_falha_no_brevo_registra_falhou(self, dados, sb, monkeypatch):
        monkeypatch.setattr(enviar_email, "brevo", BrevoFalso(falhar=True))
        sol = dict(dados["sol"], status="rejeitado", motivo_rejeicao="Registro não localizado")
        resp = enviar_email.processar(_evento("solicitacoes_certidao", "UPDATE", sol, dados["sol"]))
        assert resp["status_envio"] == "falhou"
        assert sb.tabelas["emails_enviados"][0]["status_envio"] == "falhou"
        assert sb.tabelas["emails_enviados"][0]["destinatario_email"] == "fiel@teste.local"

    def test_evento_sem_email_nao_registra(self, dados, sb, brevo_ok):
        sol = dict(dados["sol"], status="em_analise")
        assert enviar_email.processar(_evento("solicitacoes_certidao", "UPDATE", sol, dados["sol"])) == {"ignorado": True}
        assert "emails_enviados" not in sb.tabelas


# ---------------------------------------------------------------------------
# Cliente do Brevo
# ---------------------------------------------------------------------------

class TestBrevo:
    @pytest.mark.parametrize("bruto, esperado", [
        ("Certidões e Dízimo <avisos@exemplo.com>", {"name": "Certidões e Dízimo", "email": "avisos@exemplo.com"}),
        ('"Paróquia" <avisos@exemplo.com>', {"name": "Paróquia", "email": "avisos@exemplo.com"}),
        (" avisos@exemplo.com ", {"email": "avisos@exemplo.com"}),
    ])
    def test_remetente(self, monkeypatch, bruto, esperado):
        monkeypatch.setenv("EMAIL_REMETENTE", bruto)
        assert brevo.remetente() == esperado

    def test_envia_pela_api_transacional(self, monkeypatch):
        chamadas = []
        monkeypatch.setenv("BREVO_API_KEY", "chave-teste")
        monkeypatch.setenv("EMAIL_REMETENTE", "Certidões <avisos@exemplo.com>")
        monkeypatch.setattr(brevo, "requisitar", lambda *a, **k: chamadas.append((a, k)) or {"messageId": "<1@brevo>"})

        brevo.enviar("fiel@exemplo.com", "Assunto", "<p>Olá</p>")

        (metodo, url), opcoes = chamadas[0]
        assert (metodo, url) == ("POST", "https://api.brevo.com/v3/smtp/email")
        assert opcoes["headers"]["api-key"] == "chave-teste"
        assert opcoes["json_corpo"] == {
            "sender": {"name": "Certidões", "email": "avisos@exemplo.com"},
            "to": [{"email": "fiel@exemplo.com"}],
            "subject": "Assunto",
            "htmlContent": "<p>Olá</p>",
        }
