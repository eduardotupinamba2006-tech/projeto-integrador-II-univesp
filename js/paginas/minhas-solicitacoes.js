import { supabase } from '../supabase.js';
import { chamarApi, exigirPerfil } from '../sessao.js';
import { escaparHtml, formatarDataHora, SACRAMENTOS, STATUS_SOLICITACAO } from '../lib/formatacao.js';
import { mostrarPix } from '../pix.js';
import { montarCabecalho, mostrarMensagem, ocupado } from '../ui.js';

const perfil = await exigirPerfil(['publico']);
montarCabecalho();

const lista = document.getElementById('lista');
const mensagem = document.getElementById('mensagem');

function acoes(s) {
  if (s.status === 'aguardando_pagamento') {
    return `<button type="button" class="botao" data-pagar="${s.id}">Gerar Pix</button>`;
  }
  if (s.status === 'aprovado') {
    return `<button type="button" class="botao" data-baixar="${s.id}">Baixar certidão (PDF)</button>`;
  }
  if (s.status === 'rejeitado') {
    return `<strong>Motivo:</strong> ${escaparHtml(s.motivo_rejeicao)}`;
  }
  return 'Aguarde a análise da paróquia.';
}

async function carregar() {
  const { data, error } = await supabase
    .from('solicitacoes_certidao')
    .select('id, tipo, status, motivo_rejeicao, criado_em, paroquias(nome)')
    .eq('solicitante_id', perfil.id)
    .order('criado_em', { ascending: false });
  if (error) {
    lista.innerHTML = '<tr><td colspan="5">Não foi possível carregar suas solicitações.</td></tr>';
    return;
  }
  if (!data.length) {
    lista.innerHTML = '<tr><td colspan="5">Você ainda não fez nenhuma solicitação.</td></tr>';
    return;
  }
  lista.innerHTML = data.map((s) => `
    <tr>
      <td>${formatarDataHora(s.criado_em)}</td>
      <td>${SACRAMENTOS[s.tipo]}</td>
      <td>${escaparHtml(s.paroquias?.nome)}</td>
      <td><span class="etiqueta etiqueta-${s.status}">${STATUS_SOLICITACAO[s.status]}</span></td>
      <td>${acoes(s)}</td>
    </tr>`).join('');
}

lista.addEventListener('click', async (evento) => {
  const botao = evento.target.closest('button');
  if (!botao) return;
  mostrarMensagem(mensagem, '');

  if (botao.dataset.pagar) {
    ocupado(botao, true, 'Gerando Pix…');
    try {
      const pix = await chamarApi('/api/cobranca_pix', { tipo: 'taxa_certidao', solicitacao_id: botao.dataset.pagar });
      mostrarPix(document.getElementById('pix'), pix, 'Após a confirmação do pagamento, o pedido entra na fila da paróquia.');
    } catch (erro) {
      mostrarMensagem(mensagem, erro.message, 'erro');
    }
    ocupado(botao, false);
  }

  if (botao.dataset.baixar) {
    ocupado(botao, true, 'Preparando…');
    const { data, error } = await supabase.storage
      .from('certidoes')
      .createSignedUrl(`${perfil.id}/${botao.dataset.baixar}.pdf`, 60, { download: 'certidao.pdf' });
    ocupado(botao, false);
    if (error) {
      mostrarMensagem(mensagem, 'Não foi possível baixar a certidão agora. Tente novamente.', 'erro');
      return;
    }
    location.href = data.signedUrl;
  }
});

carregar();
