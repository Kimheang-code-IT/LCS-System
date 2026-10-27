import { expect, test } from '@playwright/test'

// Validation is client-side (zod schema on UAuthForm), so these assertions need
// no backend interaction and create no session. Read-only.
test.describe('login form validation', () => {
  test('an empty submit reports both field errors and stays on the page', async ({ page }) => {
    await page.goto('/auth/login')

    await page.getByRole('button', { name: 'Login', exact: true }).click()

    await expect(page.getByText('Email is required')).toBeVisible()
    await expect(page.getByText('Password is required')).toBeVisible()
    await expect(page).toHaveURL(/\/auth\/login\/?$/)
    await expect(page.locator('input[name="email"]')).toHaveAttribute('aria-invalid', 'true')
  })

  test('a malformed email is rejected before any request is sent', async ({ page }) => {
    const loginRequests: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/auth/login')) loginRequests.push(request.url())
    })

    await page.goto('/auth/login')
    await page.locator('input[name="email"]').fill('not-an-email')
    await page.locator('input[type="password"]').fill('Passw0rd!')
    await page.getByRole('button', { name: 'Login', exact: true }).click()

    await expect(page.getByText('Email is required')).toBeVisible()
    expect(loginRequests).toEqual([])
  })
})
