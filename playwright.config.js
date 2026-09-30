import { defineConfig, devices } from '@playwright/test';

// Por padrão roda contra o servidor local (scripts/servidor_dev.py + .env.local).
// No CI, E2E_BASE_URL aponta para o preview deploy da Vercel.
const baseURL = process.env.E2E_BASE_URL || 'http://localhost:3000';
const local = !process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    locale: 'pt-BR',
    trace: 'retain-on-failure',
    extraHTTPHeaders: process.env.VERCEL_AUTOMATION_BYPASS_SECRET
      ? { 'x-vercel-protection-bypass': process.env.VERCEL_AUTOMATION_BYPASS_SECRET }
      : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: local
    ? { command: 'py scripts/servidor_dev.py 3000', url: baseURL, reuseExistingServer: true }
    : undefined,
});
