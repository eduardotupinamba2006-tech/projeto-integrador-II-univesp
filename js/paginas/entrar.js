import { supabase } from '../supabase.js';
import { destinoSeguro, perfilAtual, PAGINA_INICIAL } from '../sessao.js';
import { validarEmail } from '../lib/validacao.js';
import { marcarErro, mostrarMensagem, ocupado } from '../ui.js';

const form = document.getElementById('form-entrar');
const mensagem = document.getElementById('mensagem');
const email = document.getElementById('email');
const senha = document.getElementById('senha');

async function irParaInicio() {
  const perfil = await perfilAtual();
  const volta = new URLSearchParams(location.search).get('volta');
  location.href = destinoSeguro(volta, PAGINA_INICIAL[perfil?.papel] || '/');
}

form.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  mostrarMensagem(mensagem, '');
  const validos = [
    marcarErro(email, validarEmail(email.value) ? '' : 'Informe um email válido.'),
    marcarErro(senha, senha.value ? '' : 'Informe a senha.'),
  ];
  if (validos.includes(false)) {
    form.querySelector('[aria-invalid="true"]').focus();
    return;
  }

  const botao = form.querySelector('button[type="submit"]');
  ocupado(botao, true, 'Entrando…');
  const { error } = await supabase.auth.signInWithPassword({ email: email.value.trim(), password: senha.value });
  ocupado(botao, false);

  if (error) {
    const texto = error.message.includes('Email not confirmed')
      ? 'Confirme seu email pelo link que enviamos antes de entrar.'
      : 'Email ou senha incorretos.';
    mostrarMensagem(mensagem, texto, 'erro');
    return;
  }
  irParaInicio();
});
