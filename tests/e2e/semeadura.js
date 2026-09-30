// Semeia, com a service role, solicitações já pagas para os testes fim a fim.
// Localmente lê .env.local; no CI as variáveis vêm dos secrets do GitHub.
import { createHmac } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';

function carregarEnvLocal() {
  if (!existsSync('.env.local')) return;
  for (const linha of readFileSync('.env.local', 'utf-8').split(/\r?\n/)) {
    const m = linha.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2];
  }
}

carregarEnvLocal();

const URL_SUPABASE = process.env.SUPABASE_URL;
const CHAVE = process.env.SUPABASE_SERVICE_ROLE_KEY;

async function rest(metodo, caminho, corpo) {
  const resposta = await fetch(`${URL_SUPABASE}/rest/v1/${caminho}`, {
    method: metodo,
    headers: {
      apikey: CHAVE,
      Authorization: `Bearer ${CHAVE}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
    },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  if (!resposta.ok) throw new Error(`${metodo} ${caminho}: ${resposta.status} ${await resposta.text()}`);
  return resposta.json();
}

export const PAROQUIA_A1 = 'a0000000-0000-0000-0000-0000000000a1';
export const REGISTRO_BATISMO_FIEL1 = 'b0000000-0000-0000-0000-000000000001';
const AUTH_FIEL1 = '10000000-0000-0000-0000-000000000001';

// Cria uma solicitação de batismo do fiel1 na Paróquia São Exemplo, já paga e em análise.
export async function semearSolicitacaoPaga(marcador) {
  const [perfil] = await rest('GET', `perfis?auth_user_id=eq.${AUTH_FIEL1}&select=id`);
  const [pagamento] = await rest('POST', 'pagamentos', {
    tipo: 'taxa_certidao',
    paroquia_id: PAROQUIA_A1,
    usuario_id: perfil.id,
    valor: '30.00',
    status: 'pago',
    id_transacao_externa: `e2e-${marcador}`,
  });
  const [solicitacao] = await rest('POST', 'solicitacoes_certidao', {
    solicitante_id: perfil.id,
    paroquia_id: PAROQUIA_A1,
    tipo: 'batismo',
    dados_declarados: { nome_pessoa: 'Fiel Sintético Um', observacoes: `teste e2e ${marcador}` },
    status: 'em_analise',
    pagamento_id: pagamento.id,
  });
  return solicitacao;
}

export async function lerSolicitacao(id) {
  const [linha] = await rest('GET', `solicitacoes_certidao?id=eq.${id}&select=*`);
  return linha;
}

// Mesmo formato de api/_lib/token_qr.py: "<id>.<HMAC-SHA256 em base64url sem padding>".
export function tokenQr(solicitacaoId) {
  const assinatura = createHmac('sha256', process.env.QR_SECRET).update(solicitacaoId).digest('base64url');
  return `${solicitacaoId}.${assinatura}`;
}
