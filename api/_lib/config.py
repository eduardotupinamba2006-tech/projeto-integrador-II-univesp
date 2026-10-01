"""Variáveis de ambiente. Os valores ficam só no painel da Vercel, nunca no repositório."""

import os
from decimal import Decimal

# Taxa única de emissão de certidão, igual para qualquer sacramento.
# O dízimo nunca tem taxa do sistema.
TAXA_CERTIDAO = Decimal("30.00")

BUCKET_CERTIDOES = "certidoes"


def obrigatoria(nome):
    valor = os.environ.get(nome)
    if not valor:
        raise RuntimeError("variável de ambiente ausente: " + nome)
    return valor


def supabase_url():
    return obrigatoria("SUPABASE_URL").rstrip("/")


def site_url():
    return obrigatoria("SITE_URL").rstrip("/")


def email_pagador_teste():
    """Email do comprador de teste enviado ao Mercado Pago no lugar do email da conta.

    Só existe no sandbox: as contas de demonstração usam o domínio .local, que o
    Mercado Pago recusa, e com ele o Pix de teste é aprovado automaticamente.
    Ao sair do sandbox, a variável é removida e vale o email real de quem paga.
    """
    # Espaços ou aspas colados junto com o valor no painel fazem o Mercado Pago recusar o email.
    return (os.environ.get("MP_EMAIL_PAGADOR_TESTE") or "").strip().strip('"'').strip() or None
