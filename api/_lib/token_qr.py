"""Token assinado do QR Code de validação: "<solicitacao_id>.<assinatura>"."""

import base64
import hashlib
import hmac
import uuid

from . import config


def _assinatura(solicitacao_id, segredo):
    digest = hmac.new(segredo.encode("utf-8"), solicitacao_id.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def gerar(solicitacao_id, segredo=None):
    segredo = segredo or config.obrigatoria("QR_SECRET")
    return "{}.{}".format(solicitacao_id, _assinatura(solicitacao_id, segredo))


def verificar(token, segredo=None):
    """Devolve o solicitacao_id se o token for autêntico, senão None."""
    segredo = segredo or config.obrigatoria("QR_SECRET")
    if not token or token.count(".") != 1:
        return None
    solicitacao_id, assinatura = token.split(".")
    try:
        uuid.UUID(solicitacao_id)
    except ValueError:
        return None
    if not hmac.compare_digest(assinatura, _assinatura(solicitacao_id, segredo)):
        return None
    return solicitacao_id
