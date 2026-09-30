// Validações de formulário (as mesmas regras são conferidas de novo no servidor e no banco).

export function somenteDigitos(texto) {
  return String(texto ?? '').replace(/\D/g, '');
}

export function validarCPF(cpf) {
  const d = somenteDigitos(cpf);
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  const digito = (n) => {
    let soma = 0;
    for (let i = 0; i < n; i++) soma += Number(d[i]) * (n + 1 - i);
    const resto = (soma * 10) % 11;
    return resto === 10 ? 0 : resto;
  };
  return digito(9) === Number(d[9]) && digito(10) === Number(d[10]);
}

export function formatarCPF(cpf) {
  const d = somenteDigitos(cpf).slice(0, 11);
  return d
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1-$2');
}

export function validarEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email ?? '').trim());
}

export const SENHA_MINIMA = 8;

export function validarSenha(senha) {
  return typeof senha === 'string' && senha.length >= SENHA_MINIMA;
}

export const DIZIMO_MINIMO = 1;
export const DIZIMO_MAXIMO = 100000;

// Aceita "50", "50,5", "1.234,56" ou "50.00". Devolve o valor em string com 2 casas, ou null.
export function normalizarValor(texto) {
  let t = String(texto ?? '').trim().replace(/^R\$\s*/, '');
  if (!t) return null;
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  const valor = Number(t);
  if (valor < DIZIMO_MINIMO || valor > DIZIMO_MAXIMO) return null;
  return valor.toFixed(2);
}

export function validarMotivo(motivo) {
  return String(motivo ?? '').trim().length > 0;
}
