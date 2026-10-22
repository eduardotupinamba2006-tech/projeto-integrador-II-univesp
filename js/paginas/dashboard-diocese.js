// Painel diocesano: leitura consolidada e cadastro de paróquias da própria diocese.
// A RLS já limita solicitações e pagamentos às paróquias da diocese e só deixa
// o diocesano cadastrar paróquia na diocese dele.
import { config, supabase } from '../supabase.js';
import { exigirPerfil } from '../sessao.js';
import {
  arrecadacaoPorMes, arrecadacaoPorParoquia, contarSolicitacoes, somarArrecadacao,
} from '../lib/arrecadacao.js';
import { escaparHtml, formatarMoeda } from '../lib/formatacao.js';
import { carregarGoogleMaps, geocodificar } from '../mapa.js';
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

await carregarPainel();
