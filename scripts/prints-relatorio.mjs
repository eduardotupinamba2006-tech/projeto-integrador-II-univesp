// Tira os prints do relatório final e salva em prints/.
// Por padrão usa o site publicado e as contas sintéticas do supabase/seed.sql.
// Para usar outras contas, passe por variável de ambiente (a senha nunca fica no arquivo):
//   CONTA_FIEL, CONTA_DIOCESE, SENHA, SITE e APENAS (ex.: APENAS=mapa,pix).
// Nomes e emails de pessoas aparecem cobertos por uma tarja nos prints.
// Uso: node scripts/prints-relatorio.mjs
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const SITE = process.env.SITE || 'https://projeto-integrador-ii-univesp-igreja-crm.vercel.app';
import { createInterface } from 'node:readline/promises';

// Com CONTA_FIEL definida e sem SENHA, o script pergunta a senha no terminal.
async function perguntar(texto) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const resposta = await rl.question(texto);
  rl.close();
  return resposta.trim();
}

const CONTA_FIEL = process.env.CONTA_FIEL || 'fiel1@teste.local';
const SENHA = process.env.SENHA
  || (process.env.CONTA_FIEL || process.env.CONTA_DIOCESE ? await perguntar('Senha da conta: ') : 'SenhaTeste#2026');
const CONTA_DIOCESE = process.env.CONTA_DIOCESE || 'diocese.alfa@teste.local';
const APENAS = process.env.APENAS ? process.env.APENAS.split(',') : null;
const PASTA = 'prints';
mkdirSync(PASTA, { recursive: true });

const navegador = await chromium.launch();

async function novaPagina() {
  const contexto = await navegador.newContext({
    baseURL: SITE,
    locale: 'pt-BR',
    viewport: { width: 1366, height: 900 },
    deviceScaleFactor: 2,
  });
  return contexto.newPage();
}

async function entrar(page, email, destino) {
  await page.goto('/pages/entrar.html');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Senha', { exact: true }).fill(SENHA);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.waitForURL(destino, { timeout: 30_000 });
}

// Primeira paróquia da lista de escolha (as paróquias mudam conforme o banco).
async function escolherPrimeiraParoquia(page) {
  const opcao = page.locator('#lista-paroquias input[type="radio"]').first();
  await opcao.waitFor({ timeout: 30_000 });
  await opcao.check();
}

async function etapa(chave, nome, fn) {
  if (APENAS && !APENAS.includes(chave)) return;
  try {
    await fn();
    console.log(`ok     ${nome}`);
  } catch (erro) {
    console.log(`FALHOU ${nome}: ${erro.message.split('\n')[0]}`);
  }
}

// 1. VLibras: página inicial com o botão do VLibras à direita. Não precisa de login.
await etapa('vlibras', 'novo_vlibras.png', async () => {
  const page = await novaPagina();
  await page.goto('/');
  await page.locator('#vlibras-button').waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${PASTA}/novo_vlibras.png` });
  await page.context().close();
});

// 2. Mapa e busca por endereço, na escolha de paróquia da certidão.
// Só funciona no site publicado: a chave do Google Maps é restrita ao domínio.
await etapa('mapa', 'novo_mapa.png', async () => {
  const page = await novaPagina();
  await entrar(page, CONTA_FIEL, /minhas-solicitacoes\.html/);
  await page.goto('/pages/solicitar-certidao.html');
  const mapa = page.getByRole('region', { name: 'Mapa das paróquias' });
  await mapa.locator('gmp-advanced-marker').first().waitFor({ timeout: 30_000 });
  await page.getByLabel('Paróquias perto de um endereço ou CEP').fill(process.env.ENDERECO || 'Praça da Sé, São Paulo');
  await page.getByRole('button', { name: 'Buscar' }).click();
  await page.locator('#status-paroquias').filter({ hasText: 'ordenadas pela distância' }).waitFor({ timeout: 30_000 });
  await page.getByLabel('Paróquias perto de um endereço ou CEP').scrollIntoViewIfNeeded();
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${PASTA}/novo_mapa.png` });
  await page.context().close();
});

// 3. Pix do sandbox do Mercado Pago (R$ 5,00 de dízimo de teste) confirmado na tela.
await etapa('pix', 'novo_pix_confirmado.png', async () => {
  const page = await novaPagina();
  await entrar(page, CONTA_FIEL, /minhas-solicitacoes\.html/);
  await page.goto('/pages/dizimo.html');
  await escolherPrimeiraParoquia(page);
  await page.getByLabel('Valor (R$)').fill('5,00');
  await page.getByRole('button', { name: 'Gerar Pix' }).click();
  await page.locator('#pix-situacao').filter({ hasText: 'Pagamento confirmado' }).waitFor({ timeout: 90_000 });
  await page.locator('#titulo-pix').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${PASTA}/novo_pix_confirmado.png` });
  await page.context().close();
});

// 4. Painel diocesano: cadastro de paróquia e vínculo de secretarias.
await etapa('diocese', 'novo_diocese_cadastros.png', async () => {
  const page = await novaPagina();
  await entrar(page, CONTA_DIOCESE, /dashboard-diocese\.html/);
  await page.locator('#lista-secretarias tr').first().waitFor({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  const inicio = await page.locator('section[aria-labelledby="titulo-cadastro-paroquia"]').boundingBox();
  const fim = await page.locator('section[aria-labelledby="titulo-secretarias"]').boundingBox();
  const topo = Math.max(0, inicio.y - 16);
  await page.screenshot({
    path: `${PASTA}/novo_diocese_cadastros.png`,
    fullPage: true,
    clip: { x: 0, y: topo, width: 1366, height: fim.y + fim.height + 16 - topo },
    // Nome e email das secretarias são dados pessoais: saem cobertos no print.
    maskColor: '#c9ccd6',
    mask: [page.locator('#lista-secretarias td:nth-child(2), #lista-secretarias td:nth-child(3)')],
  });
  await page.context().close();
});

await navegador.close();
console.log(`\nPrints salvos na pasta ${PASTA}/`);
