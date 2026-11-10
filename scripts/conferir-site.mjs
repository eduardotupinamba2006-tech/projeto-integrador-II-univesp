// Confere o site publicado com uma conta de fiel: a página "Minhas solicitações" (Vue 3),
// acessibilidade (axe-core) e erros no console. Não altera nada no banco.
// A conta e a senha vêm de variável de ambiente; nada fica gravado no arquivo.
// Uso: CONTA_FIEL=email SENHA=senha node scripts/conferir-site.mjs
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const SITE = process.env.SITE || 'https://projeto-integrador-ii-univesp-igreja-crm.vercel.app';
import { createInterface } from 'node:readline/promises';

// Sem SENHA no ambiente, o script pergunta a senha no terminal.
async function perguntar(texto) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const resposta = await rl.question(texto);
  rl.close();
  return resposta.trim();
}

const CONTA_FIEL = process.env.CONTA_FIEL || await perguntar('Email da conta de fiel: ');
const SENHA = process.env.SENHA || await perguntar(`Senha de ${CONTA_FIEL}: `);

let falhas = 0;
const conferir = (ok, nome, detalhe = '') => {
  console.log(`${ok ? 'ok    ' : 'FALHOU'} ${nome}${detalhe ? ` (${detalhe})` : ''}`);
  if (!ok) falhas++;
};

const navegador = await chromium.launch();
const page = await (await navegador.newContext({ baseURL: SITE, locale: 'pt-BR' })).newPage();
const erros = [];
page.on('pageerror', (e) => erros.push(e.message));
page.on('console', (m) => { if (m.type() === 'error') erros.push(m.text()); });

try {
  await page.goto('/pages/entrar.html');
  await page.getByLabel('Email').fill(CONTA_FIEL);
  await page.getByLabel('Senha', { exact: true }).fill(SENHA);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.waitForURL(/minhas-solicitacoes\.html/, { timeout: 30_000 });
  conferir(true, 'login do fiel');

  const usaVue = await page.evaluate(() => [...document.scripts].some((s) => s.src.includes('minhas-solicitacoes'))
    && !!document.querySelector('#app-solicitacoes'));
  conferir(usaVue, 'página publicada já é a versão em Vue', usaVue ? '' : 'falta fazer o push');

  await page.waitForFunction(() => !document.querySelector('#lista').innerText.includes('Carregando'), null, { timeout: 20_000 });
  const linhas = await page.locator('#lista tr').count();
  conferir(linhas > 0, 'lista de solicitações carregou', `${linhas} linha(s)`);
  conferir(!(await page.content()).includes('{{'), 'sem {{ }} sobrando na tela');
  console.log('       situações:', (await page.locator('#lista .etiqueta').allInnerTexts()).join(', ') || '(nenhuma)');
  console.log('       botões:', (await page.locator('#lista button').allInnerTexts()).join(', ') || '(nenhum)');

  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
  conferir(axe.violations.length === 0, 'acessibilidade (axe-core)', axe.violations.map((v) => v.id).join(', '));
} catch (erro) {
  conferir(false, 'teste interrompido', erro.message.split('\n')[0]);
}
conferir(erros.length === 0, 'console sem erros', erros.join(' | '));

await navegador.close();
console.log(falhas ? `\n${falhas} problema(s)` : '\nTudo certo no site publicado.');
process.exit(falhas ? 1 : 0);
