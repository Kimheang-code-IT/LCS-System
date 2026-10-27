import { expect, test } from '@playwright/test'

// Read-only smoke coverage: it needs no credentials and writes no records.
test.describe('application startup', () => {
  test('boots without an uncaught error and renders the login form', async ({ page }) => {
    const pageErrors: string[] = []
    page.on('pageerror', error => pageErrors.push(error.message))

    await page.goto('/')

    await expect(page).toHaveURL(/\/auth\/login/)
    await expect(page.getByText('Login', { exact: true }).first()).toBeVisible()
    await expect(page.locator('input[name="email"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Login', exact: true })).toBeEnabled()

    expect(pageErrors).toEqual([])
  })

  test('serves the backend on the same origin', async ({ request }) => {
    const response = await request.get('/api/v1/auth/setup/status')

    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(typeof body.data.requiresSetup).toBe('boolean')
  })
})
