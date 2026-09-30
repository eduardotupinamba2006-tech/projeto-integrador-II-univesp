"""Base dos handlers HTTP no formato das funções Python da Vercel."""

import json
from http.server import BaseHTTPRequestHandler


class Handler(BaseHTTPRequestHandler):
    def responder(self, status, corpo):
        dados = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(dados)

    def ler_corpo_bruto(self):
        tamanho = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(tamanho) if tamanho else b""

    def ler_json(self):
        bruto = self.ler_corpo_bruto()
        try:
            corpo = json.loads(bruto or b"{}")
        except ValueError:
            return None
        return corpo if isinstance(corpo, dict) else None

    def token_bearer(self):
        auth = self.headers.get("Authorization", "")
        return auth[7:].strip() if auth.lower().startswith("bearer ") else None

    def log_message(self, formato, *args):  # silencia o log padrão por requisição
        pass
