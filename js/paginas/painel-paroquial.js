import { supabase } from '../supabase.js';
import { chamarApi, exigirPerfil } from '../sessao.js';
import { arrecadacaoPorMes, somarArrecadacao } from '../lib/arrecadacao.js';
import { escaparHtml, formatarData, formatarDataHora, formatarMoeda, SACRAMENTOS } from '../lib/formatacao.js';
import { validarMotivo } from '../lib/validacao.js';
import { marcarErro, mostrarMensagem, ocupado } from '../ui.js';

const perfil = await exigirPerfil(['paroquial']);

const $ = (id) => document.getElementById(id);
const mensagem = $('mensagem');
let emAnalise = null;

const { data: paroquia } = await supabase.from('paroquias').select('nome').eq('id', perfil.paroquia_id).single();
$('nome-paroquia').textContent = paroquia ? `· ${paroquia.nome}` : '';

const referencia = (r) => [r.livro, r.folha, r.numero].map((v) => escaparHtml(v || '-')).join(' / ');

// ---------------------------------------------------------------- Fila

async function carregarFila() {
  const { data, error } = await supabase
    .from('solicitacoes_certidao')
    .select('id, tipo, dados_declarados, criado_em')
    .eq('status', 'em_analise')
    .order('criado_em');
  const corpo = $('lista-fila');
  if (error) {
    corpo.innerHTML = '<tr><td colspan="4">Não foi possível carregar a fila.</td></tr>';
    return;
  }
  if (!data.length) {
    corpo.innerHTML = '<tr><td colspan="4">Nenhuma solicitação aguardando análise.</td></tr>';
    return;
  }
  corpo.innerHTML = data.map((s) => `
    <tr>
      <td>${formatarDataHora(s.criado_em)}</td>
      <td>${SACRAMENTOS[s.tipo]}</td>
      <td>${escaparHtml(s.dados_declarados?.nome_pessoa)}</td>
      <td><button type="button" class="botao" data-analisar="${s.id}">Analisar</button></td>
    </tr>`).join('');
  corpo.querySelectorAll('[data-analisar]').forEach((botao) => {
    botao.addEventListener('click', () => abrirAnalise(data.find((s) => s.id === botao.dataset.analisar)));
  });
}

const ROTULOS_DECLARADOS = {
  nome_pessoa: 'Nome',
  data_aproximada: 'Data aproximada',
  filiacao: 'Pais',
  observacoes: 'Observações',
};

function abrirAnalise(solicitacao) {
  emAnalise = solicitacao;
  const dados = solicitacao.dados_declarados || {};
  $('titulo-analise').textContent = `Analisar solicitação de ${SACRAMENTOS[solicitacao.tipo].toLowerCase()}`;
  $('dados-declarados').innerHTML = Object.entries(ROTULOS_DECLARADOS)
    .map(([chave, rotulo]) => `<dt>${rotulo}</dt><dd>${escaparHtml(dados[chave] || 'Não informado')}</dd>`)
    .join('');
  $('busca-vinculo').value = dados.nome_pessoa || '';
  $('motivo').value = '';
  marcarErro($('motivo'), '');
  $('analise').hidden = false;
  $('titulo-analise').focus();
  buscarParaVincular();
}

function fecharAnalise() {
  emAnalise = null;
  $('analise').hidden = true;
  $('titulo-fila').focus();
}

async function buscarParaVincular() {
  let consulta = supabase
    .from('registros_sacramentais')
    .select('*')
    .eq('tipo', emAnalise.tipo)
    .order('data_sacramento')
    .limit(50);
  const termo = $('busca-vinculo').value.trim();
  if (termo) consulta = consulta.ilike('nome_pessoa', `%${termo}%`);
  const { data } = await consulta;
  const corpo = $('lista-vinculo');
  if (!data?.length) {
    corpo.innerHTML = '<tr><td colspan="4">Nenhum registro encontrado com esse nome para este sacramento.</td></tr>';
    return;
  }
  corpo.innerHTML = data.map((r) => `
    <tr>
      <td>${escaparHtml(r.nome_pessoa)}</td>
      <td>${formatarData(r.data_sacramento)}</td>
      <td>${referencia(r)}</td>
      <td><button type="button" class="botao" data-vincular="${r.id}">Vincular e emitir certidão</button></td>
    </tr>`).join('');
}

$('form-busca-vinculo').addEventListener('submit', (e) => { e.preventDefault(); buscarParaVincular(); });
$('fechar-analise').addEventListener('click', fecharAnalise);

$('lista-vinculo').addEventListener('click', async (evento) => {
  const botao = evento.target.closest('[data-vincular]');
  if (!botao) return;
  const nome = botao.closest('tr').cells[0].textContent;
  if (!confirm(`Emitir a certidão com os dados do registro de ${nome}? A certidão sai com os dados do livro.`)) return;
  ocupado(botao, true, 'Emitindo…');
  try {
    await chamarApi('/api/pdf', { solicitacao_id: emAnalise.id, registro_id: botao.dataset.vincular });
    mostrarMensagem(mensagem, 'Certidão emitida. O solicitante foi avisado por email.', 'sucesso');
    fecharAnalise();
    carregarFila();
  } catch (erro) {
    ocupado(botao, false);
    mostrarMensagem(mensagem, erro.message, 'erro');
  }
});

$('form-rejeitar').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const motivo = $('motivo');
  if (!marcarErro(motivo, validarMotivo(motivo.value) ? '' : 'Informe o motivo da rejeição.')) {
    motivo.focus();
    return;
  }
  const botao = evento.submitter;
  ocupado(botao, true, 'Rejeitando…');
  const { error } = await supabase
    .from('solicitacoes_certidao')
    .update({ status: 'rejeitado', motivo_rejeicao: motivo.value.trim() })
    .eq('id', emAnalise.id);
  ocupado(botao, false);
  if (error) {
    mostrarMensagem(mensagem, 'Não foi possível rejeitar: ' + error.message, 'erro');
    return;
  }
  mostrarMensagem(mensagem, 'Solicitação rejeitada. O solicitante recebe o motivo por email.', 'sucesso');
  fecharAnalise();
  carregarFila();
});

// ---------------------------------------------------------------- Registros

let registros = [];

async function carregarRegistros() {
  let consulta = supabase.from('registros_sacramentais').select('*').order('data_sacramento', { ascending: false }).limit(200);
  const nome = $('filtro-nome').value.trim();
  const tipo = $('filtro-tipo').value;
  if (nome) consulta = consulta.ilike('nome_pessoa', `%${nome}%`);
  if (tipo) consulta = consulta.eq('tipo', tipo);
  const { data, error } = await consulta;
  const corpo = $('lista-registros');
  if (error) {
    corpo.innerHTML = '<tr><td colspan="5">Não foi possível carregar os registros.</td></tr>';
    return;
  }
  registros = data;
  corpo.innerHTML = data.length ? data.map((r) => `
    <tr>
      <td>${escaparHtml(r.nome_pessoa)}</td>
      <td>${SACRAMENTOS[r.tipo]}</td>
      <td>${formatarData(r.data_sacramento)}</td>
      <td>${referencia(r)}</td>
      <td class="acoes">
        <button type="button" class="botao botao-secundario" data-editar="${r.id}">Editar</button>
        <button type="button" class="botao botao-perigo" data-apagar="${r.id}">Apagar</button>
      </td>
    </tr>`).join('') : '<tr><td colspan="5">Nenhum registro encontrado.</td></tr>';
}

const CAMPOS_REGISTRO = {
  tipo: 'r-tipo', nome_pessoa: 'r-nome', data_sacramento: 'r-data', livro: 'r-livro',
  folha: 'r-folha', numero: 'r-numero', celebrante: 'r-celebrante', padrinhos: 'r-padrinhos',
};

function abrirFormRegistro(registro) {
  $('registro-id').value = registro?.id || '';
  for (const [coluna, id] of Object.entries(CAMPOS_REGISTRO)) {
    $(id).value = registro?.[coluna] || (coluna === 'tipo' ? 'batismo' : '');
    marcarErro($(id), '');
  }
  $('titulo-form-registro').textContent = registro ? 'Editar registro' : 'Novo registro';
  $('form-registro').hidden = false;
  $('titulo-form-registro').focus();
}

$('form-filtro-registros').addEventListener('submit', (e) => { e.preventDefault(); carregarRegistros(); });
$('novo-registro').addEventListener('click', () => abrirFormRegistro(null));
$('cancelar-registro').addEventListener('click', () => { $('form-registro').hidden = true; $('novo-registro').focus(); });

$('lista-registros').addEventListener('click', async (evento) => {
  const botao = evento.target.closest('button');
  if (!botao) return;
  if (botao.dataset.editar) abrirFormRegistro(registros.find((r) => r.id === botao.dataset.editar));
  if (botao.dataset.apagar) {
    if (!confirm('Apagar este registro sacramental? Esta ação não pode ser desfeita.')) return;
    const { error } = await supabase.from('registros_sacramentais').delete().eq('id', botao.dataset.apagar);
    if (error) {
      const vinculado = error.code === '23503';
      mostrarMensagem(mensagem, vinculado
        ? 'Este registro já foi usado para emitir uma certidão e não pode ser apagado.'
        : 'Não foi possível apagar: ' + error.message, 'erro');
      return;
    }
    mostrarMensagem(mensagem, 'Registro apagado.', 'sucesso');
    carregarRegistros();
  }
});

$('form-registro').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const validos = [
    marcarErro($('r-nome'), $('r-nome').value.trim() ? '' : 'Informe o nome.'),
    marcarErro($('r-data'), $('r-data').value ? '' : 'Informe a data.'),
  ];
  if (validos.includes(false)) {
    evento.target.querySelector('[aria-invalid="true"]').focus();
    return;
  }
  const linha = { paroquia_id: perfil.paroquia_id };
  for (const [coluna, id] of Object.entries(CAMPOS_REGISTRO)) linha[coluna] = $(id).value.trim() || null;

  const id = $('registro-id').value;
  const botao = evento.submitter;
  ocupado(botao, true, 'Salvando…');
  const { error } = id
    ? await supabase.from('registros_sacramentais').update(linha).eq('id', id)
    : await supabase.from('registros_sacramentais').insert(linha);
  ocupado(botao, false);
  if (error) {
    mostrarMensagem(mensagem, 'Não foi possível salvar: ' + error.message, 'erro');
    return;
  }
  $('form-registro').hidden = true;
  mostrarMensagem(mensagem, id ? 'Registro atualizado.' : 'Registro criado.', 'sucesso');
  carregarRegistros();
});

// ---------------------------------------------------------------- Arrecadação

async function carregarArrecadacao() {
  const { data } = await supabase.from('pagamentos').select('tipo, status, valor, criado_em').eq('status', 'pago');
  const pagamentos = data || [];
  const totais = somarArrecadacao(pagamentos);
  $('total-dizimo').textContent = formatarMoeda(totais.dizimo);
  $('total-taxa').textContent = formatarMoeda(totais.taxa_certidao);
  $('total-geral').textContent = formatarMoeda(totais.total);
  const meses = arrecadacaoPorMes(pagamentos);
  $('lista-mensal').innerHTML = meses.length ? meses.map((m) => `
    <tr>
      <th scope="row">${m.mes.slice(5)}/${m.mes.slice(0, 4)}</th>
      <td class="numero">${formatarMoeda(m.dizimo)}</td>
      <td class="numero">${formatarMoeda(m.taxa_certidao)}</td>
      <td class="numero">${formatarMoeda(m.total)}</td>
    </tr>`).join('') : '<tr><td colspan="4">Nenhum pagamento confirmado ainda.</td></tr>';
}

carregarFila();
carregarRegistros();
carregarArrecadacao();
