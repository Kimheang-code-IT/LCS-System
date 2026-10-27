import { expect, test } from '@playwright/test'

// Every API response is intercepted. No Telegram message or real password change.
test.skip(process.env.LCS_TELEGRAM_E2E_MOCKED !== '1', 'requires explicitly opted-in mocked browser verification')
test.setTimeout(120000)

test('signed-out recovery submits a generic request after refresh refusal', async ({ page }) => {
  let requests = 0
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: { code: 'SESSION_INVALID' } })
    if (path === '/api/v1/auth/forgot-password') { requests++; return route.fulfill({ json: { data: { sent: true } } }) }
    return route.fulfill({ json: { data: path.endsWith('/setup/status') ? { requiresSetup: false } : {} } })
  })
  await page.goto('/auth/forget-password')
  await page.locator('[data-field-key="identifier"]').fill('operator')
  await page.locator('button[type="submit"]').click()
  await expect(page.getByText('If this account has an available recovery method, instructions will be sent.')).toBeVisible()
  expect(requests).toBe(1)
})

test('reset fragment is cleared, passwords validated and successful reset returns to normal login', async ({ page }) => {
  const token = 'x'.repeat(43)
  let resetBody: Record<string, string> | null = null
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    expect(route.request().url()).not.toContain(token)
    if (path === '/api/v1/auth/refresh') return route.fulfill({ status: 401, json: { code: 'SESSION_INVALID' } })
    if (path.endsWith('/forgot-password/verify')) return route.fulfill({ json: { data: { verified: true } } })
    if (path.endsWith('/forgot-password/reset')) { resetBody = route.request().postDataJSON(); return route.fulfill({ json: { data: { reset: true } } }) }
    return route.fulfill({ json: { data: path.endsWith('/setup/status') ? { requiresSetup: false } : {} } })
  })
  await page.goto(`/auth/reset-password#token=${token}`)
  await expect(page.locator('[data-field-key="password"]')).toBeVisible()
  await expect(page).toHaveURL(/\/auth\/reset-password$/)
  await page.locator('[data-field-key="password"]').fill('New-Str0ng-Password!')
  await page.locator('[data-field-key="passwordConfirmation"]').fill('different')
  await page.locator('button[type="submit"]').click()
  await expect(page).toHaveURL(/\/auth\/reset-password$/)
  expect(resetBody).toBeNull()
  await page.locator('[data-field-key="passwordConfirmation"]').fill('New-Str0ng-Password!')
  await page.locator('button[type="submit"]').click()
  await expect(page).toHaveURL(/\/auth\/login$/)
  expect(resetBody).toMatchObject({ token, password: 'New-Str0ng-Password!' })
})
