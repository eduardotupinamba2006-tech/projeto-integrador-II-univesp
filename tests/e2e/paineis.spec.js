// Painéis e RLS vistos pela interface, com os dados do seed.
import { expect, test } from '@playwright/test';
import { CONTAS, entrar, sair } from './apoio.js';

test('login redireciona cada papel para a sua página inicial', async ({ page }) => {
  await entrar(page, CONTAS.fiel1, /minhas-solicitacoes\.html/);
  await sair(page);
  await entrar(page, CONTAS.paroquiaA1, /painel-paroquial\.html/);
  await sair(page);
  await entrar(page, CONTAS.dioceseAlfa, /dashboard-diocese\.html/);
});

test('página protegida manda para o login e volta depois de entrar', async ({ page }) => {
  await page.goto('/pages/dizimo.html');
  await expect(page).toHaveURL(/entrar\.html\?volta=%2Fpages%2Fdizimo\.html/);
  await page.getByLabel('Email').fill(CONTAS.fiel1);
  await page.getByLabel('Senha').fill('SenhaTeste#2026');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/dizimo\.html$/);
});

test('papel errado é mandado para a própria página inicial', async ({ page }) => {
  await entrar(page, CONTAS.fiel1, /minhas-solicitacoes\.html/);
  await page.goto('/pages/painel-paroquial.html');
  await expect(page).toHaveURL(/minhas-solicitacoes\.html/);
});

test('login com senha errada mostra erro', async ({ page }) => {
  await page.goto('/pages/entrar.html');
  await page.getByLabel('Email').fill(CONTAS.fiel1);
  await page.getByLabel('Senha').fill('senha-errada');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('alert')).toHaveText('Email ou senha incorretos.');
});

test('painel paroquial mostra só dados da própria paróquia', async ({ page }) => {
  await entrar(page, CONTAS.paroquiaA1, /painel-paroquial\.html/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Paróquia São Exemplo');

  const registros = page.locator('#lista-registros');
  await expect(registros).toContainText('Pessoa Fictícia Três');
  // Registros de outras paróquias (Santa Amostra e N. S. do Teste) não aparecem.
  await expect(registros).not.toContainText('Noivo Fictício');
  await expect(registros).not.toContainText('Fiel Sintético Dois');

  await expect(page.locator('#total-dizimo')).not.toHaveText('…');
});

test('painel diocesano consolida só as paróquias da diocese', async ({ page }) => {
  await entrar(page, CONTAS.dioceseAlfa, /dashboard-diocese\.html/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Diocese Alfa');
  await expect(page.locator('#total-paroquias')).toHaveText('2');
  const arrecadacao = page.locator('#lista-arrecadacao');
  await expect(arrecadacao).toContainText('Paróquia São Exemplo');
  await expect(arrecadacao).toContainText('Paróquia Santa Amostra');
  await expect(arrecadacao).not.toContainText('Nossa Senhora do Teste');
  // Painel só de leitura: nenhum formulário de edição.
  await expect(page.locator('form')).toHaveCount(0);
});
