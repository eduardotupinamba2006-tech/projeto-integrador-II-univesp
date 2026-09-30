// Apoio aos testes fim a fim. As contas e a senha são as do supabase/seed.sql (dados sintéticos).
import { expect } from '@playwright/test';

export const SENHA_SEED = 'SenhaTeste#2026';

export const CONTAS = {
  fiel1: 'fiel1@teste.local',
  fiel2: 'fiel2@teste.local',
  paroquiaA1: 'paroquia.a1@teste.local',
  paroquiaA2: 'paroquia.a2@teste.local',
  dioceseAlfa: 'diocese.alfa@teste.local',
  dioceseBeta: 'diocese.beta@teste.local',
};

export async function entrar(page, email, destinoEsperado) {
  await page.goto('/pages/entrar.html');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Senha').fill(SENHA_SEED);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(destinoEsperado);
}

export async function sair(page) {
  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page).toHaveURL(/\/$/);
}
