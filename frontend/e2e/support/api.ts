import { expect, type BrowserContext, type Page } from '@playwright/test'

/** POST/PATCH with the double-submit CSRF header the SPA normally adds. */
export async function apiSend(
  context: BrowserContext,
  method: 'post' | 'patch' | 'delete',
  url: string,
  data?: Record<string, unknown>,
) {
  const cookies = await context.cookies()
  const csrf = cookies.find(cookie => cookie.name === 'XSRF-TOKEN')?.value || ''
  return context.request[method](url, {
    data,
    headers: { 'X-CSRF-Token': csrf, 'X-Requested-With': 'XMLHttpRequest' },
  })
}

/** Sign a second account in on its own context (permissions are per user). */
export async function signIn(page: Page, username: string, password: string) {
  await page.goto('/auth/login')
  await page.getByRole('textbox', { name: /email/i }).fill(username)
  await page.getByRole('textbox', { name: /password/i }).fill(password)
  await page.getByRole('button', { name: /^login$/i }).click()
  await expect(page).not.toHaveURL(/\/auth\/login/)
}
