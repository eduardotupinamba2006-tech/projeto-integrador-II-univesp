// Componentes comuns a todas as páginas: <site-cabecalho> e <site-rodape>.
// Script clássico carregado no <head>, sem defer: os elementos são definidos antes de o
// navegador ler o <body>, então o cabeçalho e o rodapé já aparecem montados, sem piscar.
// Os componentes usam o DOM normal (sem shadow DOM) para herdar o css/estilo.css.

class SiteCabecalho extends HTMLElement {
  connectedCallback() {
    // Atributo "sem-menu": páginas públicas avulsas (validação do QR Code) não mostram navegação.
    const semMenu = this.hasAttribute('sem-menu');
    this.innerHTML = `
      <a class="pular-conteudo" href="#conteudo">Pular para o conteúdo</a>
      <header class="cabecalho">
        <div class="cabecalho-conteudo">
          <a class="marca" href="/"><i class="ph-light ph-church" aria-hidden="true"></i>Certidões e Dízimo</a>
          ${semMenu ? '' : '<nav class="nav-principal" id="nav-principal" aria-label="Principal"><ul></ul></nav>'}
        </div>
      </header>`;
    // Os links do menu dependem do perfil logado; ui.js é módulo, então entra por import dinâmico.
    if (!semMenu) import('/js/ui.js').then((ui) => ui.montarCabecalho());
  }
}

class SiteRodape extends HTMLElement {
  connectedCallback() {
    this.innerHTML = '<footer class="rodape">Projeto Integrador II, UNIVESP. Todos os dados de demonstração são fictícios.</footer>';
    // Widget oficial do VLibras (versão 7): monta o próprio botão quando o script carrega.
    const vlibras = document.createElement('script');
    vlibras.src = 'https://vlibras.gov.br/app/vlibras-plugin.js';
    vlibras.defer = true;
    document.body.append(vlibras);
  }
}

customElements.define('site-cabecalho', SiteCabecalho);
customElements.define('site-rodape', SiteRodape);
