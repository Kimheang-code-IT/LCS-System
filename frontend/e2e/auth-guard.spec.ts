import { expect, test } from '@playwright/test'

// The global auth middleware redirects anonymous visitors to /auth/login and
// keeps the requested path in `redirect`. Read-only.
test.describe('authentication guard', () => {
  test('a protected deep link redirects to login and keeps the target', async ({ page }) => {
    await page.goto('/service-orders')

    await expect(page).toHaveURL(/\/auth\/login\?redirect=/)
    expect(new URL(page.url()).searchParams.get('redirect')).toMatch(/^\/service-orders\/?$/)
  })

  test('an unknown path falls back to login instead of an unauthenticated shell', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')

    await expect(page).toHaveURL(/\/auth\/login/)
  })
})
