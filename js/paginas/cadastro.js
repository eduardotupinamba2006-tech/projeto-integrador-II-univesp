import { supabase } from '../supabase.js';
import { formatarCPF, validarCPF, validarEmail, validarSenha } from '../lib/validacao.js';
import { marcarErro, mostrarMensagem, ocupado } from '../ui.js';

const form = document.getElementById('form-cadastro');
const mensagem = document.getElementById('mensagem');
const campo = (id) => document.getElementById(id);

campo('cpf').addEventListener('input', (e) => { e.target.value = formatarCPF(e.target.value); });

form.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  mostrarMensagem(mensagem, '');

  const nome = campo('nome').value.trim();
  const cpf = campo('cpf').value;
  const email = campo('email').value.trim();
  const senha = campo('senha').value;

  const validos = [
    marcarErro(campo('nome'), nome ? '' : 'Informe seu nome.'),
    marcarErro(campo('cpf'), validarCPF(cpf) ? '' : 'CPF inválido.'),
    marcarErro(campo('email'), validarEmail(email) ? '' : 'Email inválido.'),
    marcarErro(campo('senha'), validarSenha(senha) ? '' : 'A senha precisa ter pelo menos 8 caracteres.'),
    marcarErro(campo('senha2'), senha === campo('senha2').value ? '' : 'As senhas não conferem.'),
  ];
  if (validos.includes(false)) {
    form.querySelector('[aria-invalid="true"]').focus();
    return;
  }

  const botao = form.querySelector('button[type="submit"]');
  ocupado(botao, true, 'Criando conta…');
  const { data, error } = await supabase.auth.signUp({
    email,
    password: senha,
    options: {
      data: { nome, cpf: formatarCPF(cpf) },
      emailRedirectTo: location.origin + '/pages/entrar.html',
    },
  });
  ocupado(botao, false);

  if (error) {
    mostrarMensagem(mensagem, 'Não foi possível criar a conta: ' + error.message, 'erro');
    return;
  }
  form.reset();
  if (data.session) {
    location.href = '/pages/minhas-solicitacoes.html';
  } else {
    mostrarMensagem(mensagem, 'Conta criada. Enviamos um email de confirmação: abra o link para ativar sua conta e depois entre.', 'sucesso');
  }
});
