import { supabase } from '../supabase.js';
import { chamarApi, exigirPerfil } from '../sessao.js';
import { montarEscolhaParoquia } from '../escolha-paroquia.js';
import { mostrarPix } from '../pix.js';
import { marcarErro, montarCabecalho, mostrarMensagem, ocupado } from '../ui.js';

const perfil = await exigirPerfil(['publico']);
montarCabecalho();

const form = document.getElementById('form-solicitacao');
const mensagem = document.getElementById('mensagem');
const nome = document.getElementById('nome_pessoa');
const escolha = await montarEscolhaParoquia(document.getElementById('escolha-paroquia'), {
  legenda: 'Paróquia onde o sacramento foi celebrado',
});

form.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  mostrarMensagem(mensagem, '');

  const tipo = form.querySelector('input[name="tipo"]:checked')?.value;
  const paroquia = escolha?.escolhida();
  const erros = [];
  if (!tipo) erros.push('Escolha o sacramento.');
  if (!paroquia) erros.push('Escolha a paróquia.');
  if (!marcarErro(nome, nome.value.trim() ? '' : 'Informe o nome.')) erros.push('Informe o nome de quem recebeu o sacramento.');
  if (erros.length) {
    mostrarMensagem(mensagem, erros.join(' '), 'erro');
    return;
  }

  const dados = {
    nome_pessoa: nome.value.trim(),
    data_aproximada: form.data_aproximada.value.trim(),
    filiacao: form.filiacao.value.trim(),
    observacoes: form.observacoes.value.trim(),
  };

  const botao = form.querySelector('button[type="submit"]');
  ocupado(botao, true, 'Registrando pedido…');
  const { data: solicitacao, error } = await supabase
    .from('solicitacoes_certidao')
    .insert({ solicitante_id: perfil.id, paroquia_id: paroquia.id, tipo, dados_declarados: dados })
    .select('id')
    .single();
  if (error) {
    ocupado(botao, false);
    mostrarMensagem(mensagem, 'Não foi possível registrar o pedido. Tente novamente.', 'erro');
    return;
  }

  try {
    const pix = await chamarApi('/api/cobranca_pix', { tipo: 'taxa_certidao', solicitacao_id: solicitacao.id });
    form.hidden = true;
    mostrarPix(
      document.getElementById('pix'),
      pix,
      'Assim que o pagamento for confirmado, seu pedido entra na fila da paróquia e você recebe um email. Acompanhe em "Minhas solicitações".',
    );
  } catch (erro) {
    ocupado(botao, false);
    form.hidden = true;
    const aviso = document.getElementById('pix');
    aviso.hidden = false;
    aviso.innerHTML = '<p class="mensagem mensagem-erro" role="alert"></p><p><a class="botao" href="/pages/minhas-solicitacoes.html">Ir para Minhas solicitações</a></p>';
    aviso.querySelector('p').textContent = `Seu pedido foi registrado, mas o Pix não pôde ser gerado agora (${erro.message}). Você pode gerar o Pix depois em "Minhas solicitações".`;
  }
});
