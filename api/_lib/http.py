"""Cliente HTTP mínimo sobre urllib (sem SDKs de terceiros)."""

import json
import urllib.error
import urllib.request


class ErroHttp(Exception):
    def __init__(self, status, corpo):
        super().__init__("HTTP {}: {}".format(status, corpo[:500]))
        self.status = status
        self.corpo = corpo


def requisitar(metodo, url, headers=None, json_corpo=None, dados=None, timeout=15):
    """Faz a requisição e devolve o JSON decodificado (ou bytes, se não for JSON)."""
    headers = dict(headers or {})
    if json_corpo is not None:
        dados = json.dumps(json_corpo).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=dados, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read()
            tipo = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as erro:
        raise ErroHttp(erro.code, erro.read().decode("utf-8", "replace"))
    if "json" in tipo:
        return json.loads(bruto) if bruto else None
    return bruto
