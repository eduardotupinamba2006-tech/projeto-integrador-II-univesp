"""GET /api/config: configuração pública do navegador, lida das variáveis de ambiente.

Só devolve valores que podem ir para o navegador (URL do Supabase, chave publicável
e chave do Google Maps restrita por domínio). Assim cada ambiente da Vercel
(preview e produção) aponta para o seu próprio projeto sem nada fixo no código.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from _lib import config  # noqa: E402
from _lib.resposta import Handler  # noqa: E402


class handler(Handler):
    def do_GET(self):
        self.responder(200, {
            "supabaseUrl": config.supabase_url(),
            "supabaseKey": config.obrigatoria("SUPABASE_PUBLISHABLE_KEY"),
            "googleMapsKey": os.environ.get("GOOGLE_MAPS_API_KEY") or None,
        })
