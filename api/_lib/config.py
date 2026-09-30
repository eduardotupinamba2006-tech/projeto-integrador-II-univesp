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
