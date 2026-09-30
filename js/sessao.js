// Sessão, perfil e chamadas autenticadas às funções do servidor.
import { supabase } from './supabase.js';

export const PAGINA_INICIAL = {
  publico: '/pages/minhas-solicitacoes.html',
  paroquial: '/pages/painel-paroquial.html',
  diocesano: '/pages/dashboard-diocese.html',
};

export async function sessaoAtual() {
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export async function perfilAtual() {
  const sessao = await sessaoAtual();
  if (!sessao) return null;
  const { data } = await supabase.from('perfis').select('*').eq('auth_user_id', sessao.user.id).maybeSingle();
  return data;
}

// Só aceita caminhos internos, para o parâmetro ?volta= não virar redirecionamento aberto.
export function destinoSeguro(volta, padrao) {
  return volta && volta.startsWith('/') && !volta.startsWith('//') ? volta : padrao;
}

const nuncaResolve = () => new Promise(() => {});

// Garante que há alguém logado com um dos papéis indicados; senão redireciona.
export async function exigirPerfil(papeis) {
  const perfil = await perfilAtual();
  if (!perfil) {
    location.href = '/pages/entrar.html?volta=' + encodeURIComponent(location.pathname + location.search);
    return nuncaResolve();
  }
  if (papeis && !papeis.includes(perfil.papel)) {
    location.href = PAGINA_INICIAL[perfil.papel];
    return nuncaResolve();
  }
  return perfil;
}

export async function chamarApi(caminho, corpo) {
  const sessao = await sessaoAtual();
  const resposta = await fetch(caminho, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + (sessao ? sessao.access_token : ''),
    },
    body: JSON.stringify(corpo),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || 'Não foi possível concluir a operação. Tente novamente.');
  return dados;
}

export async function sair() {
  await supabase.auth.signOut();
  location.href = '/';
}
