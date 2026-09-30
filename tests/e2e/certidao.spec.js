// Fluxo de certidão a partir de uma solicitação paga (dado semeado): vínculo, PDF, download e QR Code.
import { expect, test } from '@playwright/test';
import { CONTAS, entrar, sair } from './apoio.js';
import { lerSolicitacao, REGISTRO_BATISMO_FIEL1, semearSolicitacaoPaga, tokenQr } from './semeadura.js';

test('paróquia vincula o registro, PDF é gerado, fiel baixa e o QR Code valida', async ({ page }) => {
  const solicitacao = await semearSolicitacaoPaga(`aprovar-${Date.now()}`);

  await entrar(page, CONTAS.paroquiaA1, /painel-paroquial\.html/);
  await page.locator(`[data-analisar="${solicitacao.id}"]`).click();
  await expect(page.locator('#dados-declarados')).toContainText('Fiel Sintético Um');

  page.once('dialog', (dialogo) => dialogo.accept());
  await page.locator(`[data-vincular="${REGISTRO_BATISMO_FIEL1}"]`).click();
  await expect(page.locator('#mensagem')).toHaveText(/Certidão emitida/);
  await expect(page.locator(`[data-analisar="${solicitacao.id}"]`)).toHaveCount(0);

  const aprovada = await lerSolicitacao(solicitacao.id);
  expect(aprovada.status).toBe('aprovado');
  expect(aprovada.registro_vinculado_id).toBe(REGISTRO_BATISMO_FIEL1);
  expect(aprovada.pdf_gerado_em).toBeTruthy();
  expect(aprovada.revisado_por).toBeTruthy();

  await sair(page);
  await entrar(page, CONTAS.fiel1, /minhas-solicitacoes\.html/);
  const download = page.waitForEvent('download');
  await page.locator(`[data-baixar="${solicitacao.id}"]`).click();
  const arquivo = await (await download).createReadStream();
  const pedacos = [];
  for await (const pedaco of arquivo) pedacos.push(pedaco);
  expect(Buffer.concat(pedacos).subarray(0, 4).toString()).toBe('%PDF');

  await page.goto(`/pages/validar.html?c=${tokenQr(solicitacao.id)}`);
  await expect(page.getByText('Certidão autêntica.')).toBeVisible();
  await expect(page.locator('dl')).toContainText('Fiel Sintético Um');
  await expect(page.locator('dl')).toContainText('12/03/1995');
  await expect(page.locator('dl')).toContainText('Paróquia São Exemplo');
});

test('QR Code adulterado não é reconhecido', async ({ page }) => {
  const token = tokenQr('f0000000-0000-0000-0000-000000000001');
  await page.goto(`/pages/validar.html?c=${token.slice(0, -3)}abc`);
  await expect(page.getByText('Certidão não reconhecida.')).toBeVisible();
});

test('paróquia rejeita com motivo obrigatório e o fiel vê o motivo', async ({ page }) => {
  const solicitacao = await semearSolicitacaoPaga(`rejeitar-${Date.now()}`);

  await entrar(page, CONTAS.paroquiaA1, /painel-paroquial\.html/);
  await page.locator(`[data-analisar="${solicitacao.id}"]`).click();

  await page.getByRole('button', { name: 'Rejeitar solicitação' }).click();
  await expect(page.getByLabel('Motivo da rejeição')).toHaveAttribute('aria-invalid', 'true');
  expect((await lerSolicitacao(solicitacao.id)).status).toBe('em_analise');

  const motivo = `Registro não localizado nos livros de 1990 a 2000 (e2e ${solicitacao.id.slice(0, 8)})`;
  await page.getByLabel('Motivo da rejeição').fill(motivo);
  await page.getByRole('button', { name: 'Rejeitar solicitação' }).click();
  await expect(page.locator('#mensagem')).toHaveText(/Solicitação rejeitada/);

  const rejeitada = await lerSolicitacao(solicitacao.id);
  expect(rejeitada.status).toBe('rejeitado');
  expect(rejeitada.motivo_rejeicao).toBe(motivo);

  await sair(page);
  await entrar(page, CONTAS.fiel1, /minhas-solicitacoes\.html/);
  await expect(page.locator('#lista')).toContainText(motivo);
});
