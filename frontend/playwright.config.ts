import { defineConfig, devices } from '@playwright/test'

/**
 * Browser acceptance tests for the running LCS stack.
 *
 * They exercise the real SPA against a running backend, so they create
 * records (all marked "E2E"). Point E2E_BASE_URL at an environment whose data
 * you are allowed to write to — never at production.
 *
 * Sign-in uses E2E_USER / E2E_PASSWORD (see e2e/support/fixtures.ts).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'e2e/.report' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
})
