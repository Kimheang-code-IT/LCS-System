import { expect, test as base } from '@playwright/test'

/**
 * Every test signs in through the real login form.
 *
 * A saved storage state cannot be shared between tests: refresh tokens are
 * single-use, so the second context to rotate one is refused and the session
 * dies mid-run. Signing in per test costs about a second and is deterministic.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    const user = process.env.E2E_USER
    const password = process.env.E2E_PASSWORD
    if (!user || !password) {
      throw new Error('Set E2E_USER and E2E_PASSWORD before running the browser tests.')
    }
    await page.goto('/auth/login')
    await page.getByRole('textbox', { name: /email/i }).fill(user)
    await page.getByRole('textbox', { name: /password/i }).fill(password)
    await page.getByRole('button', { name: /^login$/i }).click()
    await expect(page).not.toHaveURL(/\/auth\/login/)
    await use(page)
  },
})

export { expect }
