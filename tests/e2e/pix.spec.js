// Pix real no sandbox do Mercado Pago: a cobrança sai com o comprador de teste (APRO),
// o Mercado Pago aprova sozinho e a tela confirma o pagamento. Só roda com E2E_PIX_SANDBOX=1,
// contra um ambiente com as variáveis do Mercado Pago de teste configuradas.
import { expect, test } from '@playwright/test';
import { CONTAS, entrar } from './apoio.js';

test('dízimo pago com Pix no sandbox é confirmado na tela', async ({ page }) => {
  test.skip(process.env.E2E_PIX_SANDBOX !== '1', 'Pix do sandbox desligado neste ambiente.');

  await entrar(page, CONTAS.fiel1, /minhas-solicitacoes\.html/);
  await page.goto('/pages/dizimo.html');
  await page.getByRole('radio', { name: /Paróquia São Exemplo/ }).check();
  await page.getByLabel('Valor (R$)').fill('5,00');
  await page.getByRole('button', { name: 'Gerar Pix' }).click();

  await expect(page.getByRole('heading', { name: /Pague R\$\s5,00 com Pix/ })).toBeVisible();
  await expect(page.locator('#pix-situacao')).toHaveText('Pagamento confirmado. Obrigado!', { timeout: 60_000 });
  await expect(page.getByRole('heading', { name: /Pagamento de R\$\s5,00 confirmado/ })).toBeVisible();
});
