"""Escolha e texto dos emails disparados pelos Database Webhooks."""

from html import escape

NOMES_SACRAMENTO = {
    "batismo": "batismo",
    "primeira_comunhao": "primeira comunhão",
    "crisma": "crisma",
    "casamento": "casamento",
    "ordenacao": "ordenação",
}


def classificar(evento):
    """Recebe o payload do webhook e devolve o tipo de email, ou None se não houver email."""
    tabela = evento.get("table")
    operacao = evento.get("type")
    novo = evento.get("record") or {}
    antigo = evento.get("old_record") or {}

    if tabela == "pagamentos":
        if operacao == "INSERT":
            return "pagamento_criado_" + novo["tipo"]
        if operacao == "UPDATE" and novo.get("status") == "pago" and antigo.get("status") != "pago":
            return "recibo_dizimo" if novo["tipo"] == "dizimo" else "certidao_em_analise"

    if tabela == "solicitacoes_certidao" and operacao == "UPDATE" and novo.get("status") != antigo.get("status"):
        if novo.get("status") == "aprovado":
            return "certidao_aprovada"
        if novo.get("status") == "rejeitado":
            return "certidao_rejeitada"

    return None


def destinatario_perfil_id(evento):
    novo = evento["record"]
    return novo.get("usuario_id") or novo.get("solicitante_id")


def formatar_valor(valor):
    inteiro, _, centavos = "{:.2f}".format(float(valor)).partition(".")
    return "R$ {},{}".format("{:,}".format(int(inteiro)).replace(",", "."), centavos)


def montar(tipo, ctx):
    """ctx: nome, paroquia e, conforme o tipo, valor, sacramento, link_pdf, motivo. Devolve (assunto, html)."""
    nome = escape(ctx.get("nome") or "")
    paroquia = escape(ctx.get("paroquia") or "")
    sacramento = escape(NOMES_SACRAMENTO.get(ctx.get("sacramento"), ctx.get("sacramento") or ""))
    valor = formatar_valor(ctx["valor"]) if ctx.get("valor") is not None else ""

    if tipo == "pagamento_criado_dizimo":
        assunto = "Dízimo aguardando pagamento"
        corpo = "Recebemos sua intenção de dízimo de {} para a {}. Conclua o pagamento pelo Pix gerado no site.".format(valor, paroquia)
    elif tipo == "pagamento_criado_taxa_certidao":
        assunto = "Pedido de certidão aguardando pagamento"
        corpo = ("Recebemos seu pedido de certidão na {}. Conclua o pagamento de {} pelo Pix gerado no site "
                 "para que a paróquia comece a busca no livro de registros.").format(paroquia, valor)
    elif tipo == "recibo_dizimo":
        assunto = "Recibo de doação"
        corpo = "Confirmamos o recebimento do seu dízimo de {} para a {}. Obrigado pela sua generosidade.".format(valor, paroquia)
    elif tipo == "certidao_em_analise":
        assunto = "Pagamento confirmado: pedido em análise"
        corpo = ("Confirmamos o pagamento de {}. Seu pedido de certidão está em análise na {}. "
                 "Avisaremos por email quando houver uma resposta.").format(valor, paroquia)
    elif tipo == "certidao_aprovada":
        assunto = "Sua certidão está pronta"
        link = escape(ctx["link_pdf"], quote=True)
        corpo = ('Sua certidão de {} foi emitida pela {}. <a href="{}">Baixe o PDF aqui</a>. '
                 "O link expira em 7 dias; depois disso, baixe pela área \"Minhas solicitações\" do site.").format(sacramento, paroquia, link)
    elif tipo == "certidao_rejeitada":
        assunto = "Pedido de certidão não atendido"
        corpo = ("A {} não localizou o registro do seu pedido de certidão de {}. Motivo informado pela paróquia: "
                 "<blockquote>{}</blockquote>A taxa de emissão cobre o trabalho de busca e não é reembolsada.").format(
                     paroquia, sacramento, escape(ctx.get("motivo") or ""))
    else:
        raise ValueError("tipo de email desconhecido: " + tipo)

    html = "<p>Olá, {}.</p><p>{}</p><p>Sistema de Certidões e Dízimo Paroquial</p>".format(nome, corpo)
    return assunto, html
