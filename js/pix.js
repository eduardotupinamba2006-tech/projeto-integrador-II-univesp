// Exibe a cobrança Pix devolvida por /api/cobranca_pix.
import { escaparHtml, formatarMoeda } from './lib/formatacao.js';

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
}
