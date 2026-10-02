// Exibe a cobrança Pix devolvida por /api/cobranca_pix e acompanha a confirmação do pagamento.
import { escaparHtml, formatarMoeda } from './lib/formatacao.js';
import { chamarApi } from './sessao.js';

// Enquanto a tela do Pix estiver aberta, o servidor confere a order no Mercado Pago.
const INTERVALO_CONFERENCIA_MS = 5000;
const LIMITE_CONFERENCIA_MS = 15 * 60 * 1000;

export function mostrarPix(container, pix, textoApos) {
  container.hidden = false;
  container.innerHTML = `
    <section class="cartao pix" aria-labelledby="titulo-pix">
      <h2 id="titulo-pix" tabindex="-1">Pague ${formatarMoeda(pix.valor)} com Pix</h2>
      ${pix.qr_code_base64 ? `<img src="data:image/png;base64,${escaparHtml(pix.qr_code_base64)}" alt="QR Code do Pix no valor de ${formatarMoeda(pix.valor)}">` : ''}
      <div class="campo">
        <label for="pix-copia-cola">Pix copia e cola</label>
        <textarea id="pix-copia-cola" readonly rows="4">${escaparHtml(pix.qr_code || '')}</textarea>
      </div>
      <div class="acoes">
        <button type="button" class="botao" id="copiar-pix"><i class="ph-light ph-copy" aria-hidden="true"></i>Copiar código Pix</button>
        <span id="pix-copiado" role="status" aria-live="polite"></span>
      </div>
      <p class="mensagem" id="pix-situacao" role="status" aria-live="polite">Aguardando a confirmação do pagamento…</p>
      <p>${escaparHtml(textoApos)}</p>
    </section>`;

  container.querySelector('#copiar-pix').addEventListener('click', async () => {
    const aviso = container.querySelector('#pix-copiado');
    try {
      await navigator.clipboard.writeText(pix.qr_code || '');
      aviso.textContent = 'Código copiado.';
    } catch {
      container.querySelector('#pix-copia-cola').select();
      aviso.textContent = 'Selecione o código e copie manualmente.';
    }
  });
  container.querySelector('#titulo-pix').focus();
  acompanharPagamento(container, pix);
}

function acompanharPagamento(container, pix) {
  const inicio = Date.now();
  const secao = container.querySelector('.pix');
  const conferir = async () => {
    // Para quando a tela do Pix sai da página ou depois do limite de tempo.
    if (!secao.isConnected || Date.now() - inicio > LIMITE_CONFERENCIA_MS) return;
    try {
      const { status } = await chamarApi('/api/cobranca_pix', { tipo: 'conferir', pagamento_id: pix.pagamento_id });
      if (status === 'pago') {
        confirmar(secao, pix);
        return;
      }
    } catch {
      // Falha momentânea de rede ou do Mercado Pago: tenta de novo no próximo intervalo.
    }
    setTimeout(conferir, INTERVALO_CONFERENCIA_MS);
  };
  setTimeout(conferir, INTERVALO_CONFERENCIA_MS);
}

function confirmar(secao, pix) {
  secao.querySelector('#titulo-pix').textContent = `Pagamento de ${formatarMoeda(pix.valor)} confirmado`;
  secao.querySelectorAll('img, .campo, .acoes').forEach((elemento) => elemento.remove());
  const situacao = secao.querySelector('#pix-situacao');
  situacao.classList.add('mensagem-sucesso');
  situacao.textContent = 'Pagamento confirmado. Obrigado!';
}
