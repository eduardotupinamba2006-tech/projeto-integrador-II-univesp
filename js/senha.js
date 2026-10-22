// Botão de olho nos campos de senha: alterna entre mostrar e esconder o que foi digitado.
document.addEventListener('click', (evento) => {
  const botao = evento.target.closest('.mostrar-senha');
  if (!botao) return;
  const campo = document.getElementById(botao.getAttribute('aria-controls'));
  const mostrar = campo.type === 'password';
  campo.type = mostrar ? 'text' : 'password';
  botao.setAttribute('aria-pressed', String(mostrar));
  botao.querySelector('i').className = `ph-light ${mostrar ? 'ph-eye-slash' : 'ph-eye'}`;
});
