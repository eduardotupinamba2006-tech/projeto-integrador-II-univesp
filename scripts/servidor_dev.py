"""Servidor local de desenvolvimento e teste (nunca usado em produção).

Serve os arquivos estáticos como a Vercel e encaminha /api/<nome> para a função
api/<nome>.py, lendo as variáveis de ambiente de .env.local (não versionado).

Uso:  py scripts/servidor_dev.py [porta]      (padrão: 3000)
"""

import importlib.util
import os
import sys
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PASTA_API = os.path.join(RAIZ, "api")
sys.path.insert(0, PASTA_API)


def carregar_env(caminho):
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip().strip('"'))


def carregar_funcao(nome):
    caminho = os.path.join(PASTA_API, nome + ".py")
    if nome.startswith("_") or not os.path.isfile(caminho):
        return None
    spec = importlib.util.spec_from_file_location("api_" + nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.handler


class Roteador(SimpleHTTPRequestHandler):
    def _api(self, metodo):
        caminho = urllib.parse.urlparse(self.path).path
        if not caminho.startswith("/api/"):
            return False
        funcao = carregar_funcao(caminho[len("/api/"):].strip("/"))
        acao = getattr(funcao, metodo, None) if funcao else None
        if not acao:
            self.send_error(404 if not funcao else 405)
            return True
        # Executa o método da função sobre esta requisição (mesma interface BaseHTTPRequestHandler).
        for nome in ("responder", "ler_corpo_bruto", "ler_json", "token_bearer"):
            setattr(self, nome, getattr(funcao, nome).__get__(self))
        acao(self)
        return True

    def do_GET(self):
        if not self._api("do_GET"):
            super().do_GET()

    def do_POST(self):
        if not self._api("do_POST"):
            self.send_error(405)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    carregar_env(os.path.join(RAIZ, ".env.local"))
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), partial(Roteador, directory=RAIZ))
    print("Servidor de desenvolvimento em http://localhost:{}".format(porta))
    servidor.serve_forever()


if __name__ == "__main__":
    main()
