// Painel diocesano: leitura consolidada, cadastro de paróquias e vínculo de secretarias da própria diocese.
// A RLS já limita solicitações e pagamentos às paróquias da diocese e só deixa
// o diocesano cadastrar paróquia na diocese dele.
import { config, supabase } from '../supabase.js';
import { exigirPerfil } from '../sessao.js';
import {
  arrecadacaoPorMes, arrecadacaoPorParoquia, contarSolicitacoes, somarArrecadacao,
} from '../lib/arrecadacao.js';
import { escaparHtml, formatarMoeda } from '../lib/formatacao.js';
import { carregarGoogleMaps, geocodificar } from '../mapa.js';
import { validarEmail } from '../lib/validacao.js';
import { marcarErro, mostrarMensagem, ocupado } from '../ui.js';

const perfil = await exigirPerfil(['diocesano']);

const $ = (id) => document.getElementById(id);

async function carregarPainel() {
  const [diocese, paroquias, solicitacoes, pagamentos] = await Promise.all([
    supabase.from('dioceses').select('nome').eq('id', perfil.diocese_id).single(),
    supabase.from('paroquias').select('id, nome').eq('diocese_id', perfil.diocese_id).order('nome'),
    supabase.from('solicitacoes_certidao').select('paroquia_id, status'),
    supabase.from('pagamentos').select('paroquia_id, tipo, status, valor, criado_em').eq('status', 'pago'),
  ]);

  if (paroquias.error || solicitacoes.error || pagamentos.error) {
    mostrarMensagem($('mensagem'), 'Não foi possível carregar todos os dados do painel. Recarregue a página.', 'erro');
  }

  const listaParoquias = paroquias.data || [];
  const listaSolicitacoes = solicitacoes.data || [];
  const listaPagamentos = pagamentos.data || [];

  $('nome-diocese').textContent = diocese.data ? `· ${diocese.data.nome}` : '';

  const contagem = contarSolicitacoes(listaSolicitacoes);
  const totais = somarArrecadacao(listaPagamentos);
  $('total-paroquias').textContent = listaParoquias.length;
  $('total-solicitadas').textContent = contagem.total;
  $('total-aprovadas').textContent = contagem.aprovado;
  $('total-dizimos').textContent = formatarMoeda(totais.dizimo);
  $('total-taxas').textContent = formatarMoeda(totais.taxa_certidao);

  $('lista-certidoes').innerHTML = listaParoquias.map((p) => {
    const c = contarSolicitacoes(listaSolicitacoes.filter((s) => s.paroquia_id === p.id));
    return `
      <tr>
        <th scope="row">${escaparHtml(p.nome)}</th>
        <td class="numero">${c.total}</td>
        <td class="numero">${c.aguardando_pagamento}</td>
        <td class="numero">${c.em_analise}</td>
        <td class="numero">${c.aprovado}</td>
        <td class="numero">${c.rejeitado}</td>
      </tr>`;
  }).join('') || '<tr><td colspan="6">Nenhuma paróquia cadastrada.</td></tr>';

  $('lista-arrecadacao').innerHTML = arrecadacaoPorParoquia(listaPagamentos, listaParoquias).map((linha) => `
    <tr>
      <th scope="row">${escaparHtml(linha.paroquia.nome)}</th>
      <td class="numero">${formatarMoeda(linha.dizimo)}</td>
      <td class="numero">${formatarMoeda(linha.taxa_certidao)}</td>
      <td class="numero">${formatarMoeda(linha.total)}</td>
    </tr>`).join('') || '<tr><td colspan="4">Nenhuma paróquia cadastrada.</td></tr>';

  const meses = arrecadacaoPorMes(listaPagamentos);
  $('lista-mensal').innerHTML = meses.map((m) => `
    <tr>
      <th scope="row">${m.mes.slice(5)}/${m.mes.slice(0, 4)}</th>
      <td class="numero">${formatarMoeda(m.dizimo)}</td>
      <td class="numero">${formatarMoeda(m.taxa_certidao)}</td>
      <td class="numero">${formatarMoeda(m.total)}</td>
    </tr>`).join('') || '<tr><td colspan="4">Nenhum pagamento confirmado ainda.</td></tr>';

  const seletor = $('secretaria-paroquia');
  const escolhida = seletor.value;
  seletor.innerHTML = listaParoquias.length
    ? listaParoquias.map((p) => `<option value="${p.id}">${escaparHtml(p.nome)}</option>`).join('')
    : '<option value="">Cadastre uma paróquia primeiro</option>';
  if (listaParoquias.some((p) => p.id === escolhida)) seletor.value = escolhida;

  await carregarSecretarias();
}

async function carregarSecretarias() {
  const { data, error } = await supabase.rpc('secretarias_da_diocese');
  if (error) {
    $('lista-secretarias').innerHTML = '<tr><td colspan="4">Não foi possível carregar as secretarias.</td></tr>';
    return;
  }
  $('lista-secretarias').innerHTML = data.map((s) => `
    <tr>
      <th scope="row">${escaparHtml(s.paroquia)}</th>
      <td>${escaparHtml(s.nome)}</td>
      <td>${escaparHtml(s.email)}</td>
      <td><button type="button" class="botao botao-secundario" data-desvincular="${s.perfil_id}" aria-label="Desvincular ${escaparHtml(s.nome || s.email)} de ${escaparHtml(s.paroquia)}">Desvincular</button></td>
    </tr>`).join('') || '<tr><td colspan="4">Nenhuma secretaria vinculada.</td></tr>';
}

// Coordenadas do endereço pelo Google Maps, quando a chave estiver disponível neste endereço.
// Sem elas a paróquia é cadastrada mesmo assim, só não aparece no mapa nem na busca por proximidade.
async function coordenadas(endereco) {
  if (!config.googleMapsKey) return null;
  try {
    return await geocodificar(await carregarGoogleMaps(config.googleMapsKey), endereco);
  } catch {
    return null;
  }
}

const form = $('form-paroquia');
form.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const nome = $('paroquia-nome');
  const endereco = $('paroquia-endereco');
  const mensagem = $('mensagem-paroquia');
  mostrarMensagem(mensagem, '');

  const nomeOk = marcarErro(nome, nome.value.trim() ? '' : 'Informe o nome da paróquia.');
  const enderecoOk = marcarErro(endereco, endereco.value.trim() ? '' : 'Informe o endereço da paróquia.');
  if (!nomeOk || !enderecoOk) {
    (nomeOk ? endereco : nome).focus();
    return;
  }

  const botao = form.querySelector('button[type="submit"]');
  ocupado(botao, true, 'Cadastrando…');
  const local = await coordenadas(endereco.value.trim());
  const { error } = await supabase.from('paroquias').insert({
    diocese_id: perfil.diocese_id,
    nome: nome.value.trim(),
    endereco: endereco.value.trim(),
    lat: local?.lat ?? null,
    lng: local?.lng ?? null,
  });
  ocupado(botao, false);

  if (error) {
    mostrarMensagem(mensagem, 'Não foi possível cadastrar a paróquia. Tente novamente.', 'erro');
    return;
  }
  mostrarMensagem(
    mensagem,
    local
      ? `${nome.value.trim()} foi cadastrada e já aparece no mapa.`
      : `${nome.value.trim()} foi cadastrada. O endereço não foi localizado no mapa, então ela não aparece na busca por proximidade.`,
    'sucesso',
  );
  form.reset();
  await carregarPainel();
});

const formSecretaria = $('form-secretaria');
formSecretaria.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const email = $('secretaria-email');
  const paroquia = $('secretaria-paroquia');
  const mensagem = $('mensagem-secretaria');
  mostrarMensagem(mensagem, '');

  if (!marcarErro(email, validarEmail(email.value) ? '' : 'Informe um email válido.')) {
    email.focus();
    return;
  }
  if (!paroquia.value) {
    mostrarMensagem(mensagem, 'Cadastre uma paróquia antes de vincular uma secretaria.', 'erro');
    return;
  }

  const botao = formSecretaria.querySelector('button[type="submit"]');
  ocupado(botao, true, 'Vinculando…');
  const { error } = await supabase.rpc('vincular_secretaria', { p_email: email.value.trim(), p_paroquia_id: paroquia.value });
  ocupado(botao, false);

  if (error) {
    // As mensagens das funções do banco já são escritas para quem usa o painel.
    const conhecida = ['P0002', '42501'].includes(error.code);
    mostrarMensagem(mensagem, conhecida ? error.message : 'Não foi possível vincular a secretaria. Tente novamente.', 'erro');
    return;
  }
  const nomeParoquia = paroquia.options[paroquia.selectedIndex].text;
  mostrarMensagem(mensagem, `${email.value.trim()} agora é secretaria da ${nomeParoquia}. No próximo login, a conta entra no painel paroquial.`, 'sucesso');
  email.value = '';
  await carregarSecretarias();
});

$('lista-secretarias').addEventListener('click', async (evento) => {
  const botao = evento.target.closest('[data-desvincular]');
  if (!botao) return;
  if (!window.confirm('Desvincular esta secretaria? A conta continua existindo, mas volta a ser uma conta comum de fiel.')) return;
  ocupado(botao, true, 'Desvinculando…');
  const { error } = await supabase.rpc('desvincular_secretaria', { p_perfil_id: botao.dataset.desvincular });
  if (error) {
    ocupado(botao, false);
    mostrarMensagem($('mensagem-secretaria'), 'Não foi possível desvincular a secretaria. Tente novamente.', 'erro');
    return;
  }
  mostrarMensagem($('mensagem-secretaria'), 'Secretaria desvinculada.', 'sucesso');
  await carregarSecretarias();
});

await carregarPainel();
