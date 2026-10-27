import { expect, test } from '@playwright/test'

/**
 * Authenticated journey. It is skipped unless a dedicated, non-production test
 * account is supplied, so an ordinary run never touches real records:
 *
 *   E2E_USERNAME=e2e@example.test E2E_PASSWORD=... pnpm test:e2e
 *
 * Nothing here creates, edits or deletes data.
 */
const username = process.env.E2E_USERNAME
const password = process.env.E2E_PASSWORD

test.describe('signed-in navigation', () => {
  test.skip(!username || !password, 'Set E2E_USERNAME and E2E_PASSWORD to run the authenticated journey.')

  test('a signed-in user leaves the login page and can open a protected list', async ({ page }) => {
    await page.goto('/auth/login')
    await page.locator('input[name="email"]').fill(username!)
    await page.locator('input[type="password"]').fill(password!)
    await page.getByRole('button', { name: 'Login', exact: true }).click()

    await expect(page).not.toHaveURL(/\/auth\/login/)
    await expect(page.locator('input[name="email"]')).toHaveCount(0)

    await page.goto('/quotations')
    await expect(page).not.toHaveURL(/\/auth\/login/)
  })

  test('signing out returns to the login screen', async ({ page }) => {
    await page.goto('/auth/login')
    await page.locator('input[name="email"]').fill(username!)
    await page.locator('input[type="password"]').fill(password!)
    await page.getByRole('button', { name: 'Login', exact: true }).click()
    await expect(page).not.toHaveURL(/\/auth\/login/)

    // The account menu lives in the app header; the trigger is labelled with the
    // signed-in user's name, so it is located by role rather than by copy.
    await page.getByRole('button', { name: new RegExp(username!, 'i') }).click()
    await page.getByRole('menuitem', { name: /sign out|log out/i }).click()

    await expect(page).toHaveURL(/\/auth\/login/)
  })
})
