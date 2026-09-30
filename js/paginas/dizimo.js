import { supabase } from '../supabase.js';
import { chamarApi, exigirPerfil } from '../sessao.js';
import { montarEscolhaParoquia } from '../escolha-paroquia.js';
import { normalizarValor } from '../lib/validacao.js';
import { mostrarPix } from '../pix.js';
import { marcarErro, montarCabecalho, mostrarMensagem, ocupado } from '../ui.js';

const perfil = await exigirPerfil(['publico']);
montarCabecalho();

const form = document.getElementById('form-dizimo');
const mensagem = document.getElementById('mensagem');
const valor = document.getElementById('valor');
const cadastrar = document.getElementById('cadastrar');
const situacao = document.getElementById('situacao-dizimista');

const { data: cadastros } = await supabase.from('dizimistas').select('paroquia_id').eq('perfil_id', perfil.id);
const paroquiasDizimista = new Set((cadastros || []).map((c) => c.paroquia_id));

const escolha = await montarEscolhaParoquia(document.getElementById('escolha-paroquia'), {
  legenda: 'Paróquia',
  aoEscolher(paroquia) {
    const jaCadastrado = paroquiasDizimista.has(paroquia.id);
    cadastrar.checked = jaCadastrado;
    cadastrar.disabled = jaCadastrado;
    situacao.textContent = jaCadastrado ? '(você já é dizimista desta paróquia)' : '';
  },
});

form.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  mostrarMensagem(mensagem, '');

  const paroquia = escolha?.escolhida();
  const valorNormalizado = normalizarValor(valor.value);
  const erros = [];
  if (!paroquia) erros.push('Escolha a paróquia.');
  if (!marcarErro(valor, valorNormalizado ? '' : 'Informe um valor entre R$ 1,00 e R$ 100.000,00.')) {
    erros.push('Informe um valor válido.');
  }
  if (erros.length) {
    mostrarMensagem(mensagem, erros.join(' '), 'erro');
    return;
  }

  const botao = form.querySelector('button[type="submit"]');
  ocupado(botao, true, 'Gerando Pix…');

  if (cadastrar.checked && !paroquiasDizimista.has(paroquia.id)) {
    const { error } = await supabase.from('dizimistas').insert({ perfil_id: perfil.id, paroquia_id: paroquia.id });
    if (error) {
      ocupado(botao, false);
      mostrarMensagem(mensagem, 'Não foi possível fazer seu cadastro de dizimista. Tente novamente.', 'erro');
      return;
    }
    paroquiasDizimista.add(paroquia.id);
  }

  try {
    const pix = await chamarApi('/api/cobranca_pix', { tipo: 'dizimo', paroquia_id: paroquia.id, valor: valorNormalizado });
    form.hidden = true;
    mostrarPix(
      document.getElementById('pix'),
      pix,
      'Assim que o pagamento for confirmado, você recebe o recibo da doação por email. Obrigado!',
    );
  } catch (erro) {
    ocupado(botao, false);
    mostrarMensagem(mensagem, erro.message, 'erro');
  }
});
