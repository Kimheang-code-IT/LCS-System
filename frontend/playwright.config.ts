import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end target.
 *
 * The docker compose stack (`infrastructure/docker-compose.yml`) serves the built
 * SPA at http://localhost through nginx, which also proxies /api to the backend,
 * so the browser sees one same-origin application. Point E2E_BASE_URL at an
 * alternative origin (for example `pnpm dev` on http://localhost:3000) when the
 * stack is not running.
 *
 * `e2e/` is deliberately outside `tests/`, which is the Vitest unit suite.
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
