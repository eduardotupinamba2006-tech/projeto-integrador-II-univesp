// Google Maps na escolha de paróquia. A chave é restrita ao domínio da Vercel, então
// este teste só roda contra o site publicado (E2E_BASE_URL) com GOOGLE_MAPS_API_KEY configurada.
import { expect, test } from '@playwright/test';
import { CONTAS, entrar } from './apoio.js';

test('mapa mostra as paróquias e a busca por endereço ordena pela distância', async ({ page, request }) => {
  const config = await (await request.get('/api/config')).json();
  test.skip(!config.googleMapsKey || !process.env.E2E_BASE_URL, 'Sem chave do Google Maps válida para este endereço.');

  await entrar(page, CONTAS.fiel1, /minhas-solicitacoes\.html/);
  await page.goto('/pages/solicitar-certidao.html');

  const mapa = page.getByRole('region', { name: 'Mapa das paróquias' });
  await expect(mapa).toBeVisible();
  // Um marcador por paróquia com coordenadas (3 no seed).
  await expect(mapa.locator('gmp-advanced-marker')).toHaveCount(3, { timeout: 20000 });

  // Endereço público de referência, perto da Paróquia Santa Amostra (Pinheiros).
  await page.getByLabel('Paróquias perto de um endereço ou CEP').fill('Largo da Batata, Pinheiros, São Paulo');
  await page.getByRole('button', { name: 'Buscar' }).click();
  await expect(page.locator('#status-paroquias')).toContainText('Paróquias ordenadas pela distância até');
  await expect(page.locator('#lista-paroquias .opcao').first()).toContainText('Paróquia Santa Amostra');

  // Clicar no marcador escolhe a mesma paróquia na lista.
  await mapa.locator('gmp-advanced-marker[title="Paróquia São Exemplo"]').click();
  await expect(page.getByRole('radio', { name: /Paróquia São Exemplo/ })).toBeChecked();
});
