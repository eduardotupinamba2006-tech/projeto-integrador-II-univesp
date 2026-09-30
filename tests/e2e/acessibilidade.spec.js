// Acessibilidade: nenhuma violação WCAG 2.x A/AA detectada pelo axe-core, nos modos claro e escuro.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { CONTAS, entrar } from './apoio.js';

const PUBLICAS = [
  '/',
  '/pages/entrar.html',
  '/pages/cadastro.html',
  '/pages/recuperar-senha.html',
  '/pages/nova-senha.html',
  '/pages/validar.html?c=invalido',
];

const LOGADAS = [
  [CONTAS.fiel1, /minhas-solicitacoes/, ['/pages/minhas-solicitacoes.html', '/pages/solicitar-certidao.html', '/pages/dizimo.html']],
  [CONTAS.paroquiaA1, /painel-paroquial/, ['/pages/painel-paroquial.html']],
  [CONTAS.dioceseAlfa, /dashboard-diocese/, ['/pages/dashboard-diocese.html']],
];

async function semViolacoes(page) {
  // Espera o conteúdo carregado pelo JS (listas, tabelas) antes de analisar.
  await page.waitForLoadState('networkidle');
  const resultado = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  const resumo = resultado.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
  expect(resumo).toEqual([]);
}

for (const esquema of ['light', 'dark']) {
  test.describe(`modo ${esquema === 'light' ? 'claro' : 'escuro'}`, () => {
    test.use({ colorScheme: esquema });

    for (const caminho of PUBLICAS) {
      test(`página pública ${caminho}`, async ({ page }) => {
        await page.goto(caminho);
        await semViolacoes(page);
      });
    }

    for (const [conta, destino, paginas] of LOGADAS) {
      test(`páginas de ${conta}`, async ({ page }) => {
        await entrar(page, conta, destino);
        for (const caminho of paginas) {
          await page.goto(caminho);
          await semViolacoes(page);
        }
      });
    }
  });
}
