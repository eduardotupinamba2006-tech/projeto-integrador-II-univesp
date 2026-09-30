// Utilidades de interface: cabeçalho, mensagens acessíveis e erros de campo.
import { perfilAtual, sair, PAGINA_INICIAL } from './sessao.js';

export function mostrarMensagem(elemento, texto, tipo = 'info') {
  elemento.textContent = texto || '';
  elemento.className = 'mensagem mensagem-' + tipo;
}

// Marca o campo como inválido e liga a mensagem de erro a ele (aria-describedby).
export function marcarErro(campo, texto) {
  const idErro = campo.id + '-erro';
  let erro = document.getElementById(idErro);
  if (!erro) {
    erro = document.createElement('span');
    erro.id = idErro;
    erro.className = 'dica mensagem-erro';
    campo.insertAdjacentElement('afterend', erro);
  }
  erro.textContent = texto || '';
  if (texto) {
    campo.setAttribute('aria-invalid', 'true');
    campo.setAttribute('aria-describedby', [campo.dataset.dica, idErro].filter(Boolean).join(' '));
  } else {
    campo.removeAttribute('aria-invalid');
    if (campo.dataset.dica) campo.setAttribute('aria-describedby', campo.dataset.dica);
    else campo.removeAttribute('aria-describedby');
  }
  return !texto;
}

function item(conteudo) {
  const li = document.createElement('li');
  li.append(conteudo);
  return li;
}

function link(texto, href) {
  const a = document.createElement('a');
  a.href = href;
  a.textContent = texto;
  if (location.pathname === href) a.setAttribute('aria-current', 'page');
  return a;
}

export async function montarCabecalho() {
  const lista = document.querySelector('#nav-principal ul');
  if (!lista) return;
  const perfil = await perfilAtual();
  const itens = [];
  if (!perfil || perfil.papel === 'publico') {
    itens.push(link('Solicitar certidão', '/pages/solicitar-certidao.html'));
    itens.push(link('Dízimo', '/pages/dizimo.html'));
  }
  if (perfil) {
    if (perfil.papel === 'publico') itens.push(link('Minhas solicitações', PAGINA_INICIAL.publico));
    if (perfil.papel === 'paroquial') itens.push(link('Painel da paróquia', PAGINA_INICIAL.paroquial));
    if (perfil.papel === 'diocesano') itens.push(link('Painel da diocese', PAGINA_INICIAL.diocesano));
    const botao = document.createElement('button');
    botao.type = 'button';
    botao.textContent = 'Sair';
    botao.addEventListener('click', sair);
    itens.push(botao);
  } else {
    itens.push(link('Entrar', '/pages/entrar.html'));
    itens.push(link('Criar conta', '/pages/cadastro.html'));
  }
  lista.replaceChildren(...itens.map(item));
}

export function ocupado(botao, estaOcupado, textoOcupado = 'Aguarde…') {
  if (estaOcupado) {
    botao.dataset.textoOriginal = botao.textContent;
    botao.textContent = textoOcupado;
    botao.disabled = true;
    botao.setAttribute('aria-busy', 'true');
  } else {
    botao.textContent = botao.dataset.textoOriginal || botao.textContent;
    botao.disabled = false;
    botao.removeAttribute('aria-busy');
  }
}
