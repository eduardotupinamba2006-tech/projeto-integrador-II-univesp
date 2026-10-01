"""Dublês em memória do Supabase, Mercado Pago e Resend para testar as funções da pasta api/."""

import copy
import uuid


class SupabaseFalso:
    """Imita o módulo api/_lib/supabase.py com tabelas em memória (sem RLS, como a service role)."""

    def __init__(self):
        self.tabelas = {}
        self.arquivos = {}
        self.emails = {}  # perfil_id -> (email, nome)

    def semear(self, tabela, linha):
        linha = dict(linha)
        if not linha.get("id"):
            linha["id"] = str(uuid.uuid4())
        self.tabelas.setdefault(tabela, []).append(linha)
        return linha

    def _filtra(self, tabela, filtros):
        linhas = self.tabelas.get(tabela, [])
        condicoes = {k: v[3:] for k, v in filtros.items() if k != "select" and v.startswith("eq.")}
        return [l for l in linhas if all(str(l.get(k)) == v for k, v in condicoes.items())]

    def selecionar(self, tabela, filtros):
        resultado = [copy.deepcopy(l) for l in self._filtra(tabela, filtros)]
        if tabela == "registros_sacramentais" and "paroquias(" in filtros.get("select", ""):
            for linha in resultado:
                paroquia = dict(self._filtra("paroquias", {"id": "eq." + linha["paroquia_id"]})[0])
                paroquia["dioceses"] = self._filtra("dioceses", {"id": "eq." + paroquia["diocese_id"]})[0]
                linha["paroquias"] = paroquia
        return resultado

    def selecionar_um(self, tabela, filtros):
        linhas = self.selecionar(tabela, filtros)
        return linhas[0] if linhas else None

    def inserir(self, tabela, linha):
        linha = dict(linha)
        if tabela == "pagamentos":
            linha.setdefault("status", "pendente")
            linha.setdefault("id_transacao_externa", None)
        return copy.deepcopy(self.semear(tabela, linha))

    def atualizar(self, tabela, filtros, valores):
        linhas = self._filtra(tabela, filtros)
        for linha in linhas:
            linha.update(valores)
        return [copy.deepcopy(l) for l in linhas]

    def usuario_do_token(self, jwt):
        return None

    def perfil_do_token(self, jwt):
        return None

    def email_do_perfil(self, perfil_id):
        return self.emails.get(perfil_id, (None, None))

    def enviar_arquivo(self, bucket, caminho, conteudo, tipo):
        self.arquivos[(bucket, caminho)] = (conteudo, tipo)

    def url_assinada(self, bucket, caminho, segundos):
        return "https://supabase.teste/storage/v1/object/sign/{}/{}?token=x".format(bucket, caminho)


class MercadoPagoFalso:
    def __init__(self):
        self.cobrancas = []
        self.pagamentos = {}
        self._proximo = 1000

    def criar_pix(self, pagamento_id, valor, descricao, pagador):
        self._proximo += 1
        self.cobrancas.append({"pagamento_id": pagamento_id, "valor": valor, "descricao": descricao, "pagador": pagador})
        return {"id": str(self._proximo), "qr_code": "000201PIX", "qr_code_base64": "iVBOR", "ticket_url": "https://mp.teste"}

    def consultar(self, id_externo):
        return self.pagamentos[str(id_externo)]


class ResendFalso:
    def __init__(self, falhar=False):
        self.enviados = []
        self.falhar = falhar

    def enviar(self, para, assunto, html):
        if self.falhar:
            raise RuntimeError("Resend indisponível")
        self.enviados.append({"para": para, "assunto": assunto, "html": html})
        return {"id": "email-teste"}
