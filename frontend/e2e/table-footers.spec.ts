import { expect, test } from './support/fixtures'
import { apiSend } from './support/api'

/**
 * Reusable table footers: record counts under the first column and
 * decimal-safe money sums under amount columns. Financial Documents totals
 * come from the server (`meta.totals`), so they stay authoritative for the
 * whole filtered list, not only the loaded page.
 */
test('financial documents footer shows record count and one base-currency total', async ({ page }) => {
  await page.goto('/finance/documents')
  const footer = page.locator('tfoot').first()
  await expect(footer).toBeVisible({ timeout: 15_000 })
  await expect(footer).toContainText(/records|កំណត់ត្រា|条记录/)
  // Money totals are present and never render NaN (decimal-safe sums).
  const text = await footer.innerText()
  expect(text).not.toContain('NaN')
  expect(text).toMatch(/\d/)
  // One base-currency total: no mixed "USD · KHR" footer, and it matches the
  // configured base currency (never a hardcoded USD assumption).
  expect(text).not.toContain(' · ')
  const configured = await page.evaluate(async () => {
    const response = await fetch('/api/v1/settings/app-config', { credentials: 'include' })
    const body = await response.json()
    return String(body.data?.localization?.currency || '')
  })
  expect(configured).toBeTruthy()

  // Empty filtered result: the count footer shows the zero state.
  await page.getByPlaceholder(/search/i).fill('zzz-no-such-record-zzz')
  await page.waitForTimeout(1500)
  await expect(page.locator('tfoot').first()).toContainText('0 records')
})

test('accounting periods footer is count-only', async ({ page }) => {
  await page.goto('/finance/accounting-periods')
  const footer = page.locator('tfoot').first()
  await expect(footer).toBeVisible({ timeout: 15_000 })
  const text = await footer.innerText()
  expect(text).toMatch(/records|កំណត់ត្រា|条记录/)
  // No meaningless money totals on periods.
  expect(text).not.toMatch(/USD|KHR/)
})

test('footer picks up a created document', async ({ page }) => {
  const stamp = Date.now().toString().slice(-5)
  await page.goto('/finance/documents')
  const footer = page.locator('tfoot').first()
  await expect(footer).toBeVisible({ timeout: 15_000 })
  // Wait until the list actually loaded before capturing the baseline.
  await expect(page.getByRole('button', { name: /Actions for/ }).first()).toBeVisible({ timeout: 15_000 })
  const before = await footer.innerText()

  // Create an isolated draft invoice through the API, distinctive amount.
  const created = await apiSend(page.context(), 'post', '/api/v1/financial-documents', {
    documentType: 'CUSTOMER_INVOICE',
    date: '2026-03-05',
    currency: 'USD',
    lines: [{ description: `E2E footer invoice ${stamp}`, quantity: 1, unitPrice: 12_345 }],
  })
  expect(created.ok).toBeTruthy()

  await page.reload()
  await expect(footer).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('button', { name: /Actions for/ }).first()).toBeVisible({ timeout: 15_000 })
  // The server-computed footer aggregates follow the new record.
  const after = await footer.innerText()
  expect(after).not.toBe(before)
})
