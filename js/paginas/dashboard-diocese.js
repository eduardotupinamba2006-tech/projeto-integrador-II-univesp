// Painel diocesano: só leitura. A RLS já limita solicitações e pagamentos às paróquias da diocese.
import { supabase } from '../supabase.js';
import { exigirPerfil } from '../sessao.js';
import {
  arrecadacaoPorMes, arrecadacaoPorParoquia, contarSolicitacoes, somarArrecadacao,
} from '../lib/arrecadacao.js';
import { escaparHtml, formatarMoeda } from '../lib/formatacao.js';
import { montarCabecalho, mostrarMensagem } from '../ui.js';

const perfil = await exigirPerfil(['diocesano']);
montarCabecalho();

const $ = (id) => document.getElementById(id);

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
