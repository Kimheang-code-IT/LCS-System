import { expect, test } from './support/fixtures'

/**
 * Read-only report smoke: every approved report renders without a server error.
 * A report page must never write or allocate anything, so nothing is submitted.
 */
const REPORTS = [
  ['/reports/finance/trial-balance', 'Trial Balance'],
  ['/reports/finance/profit-loss', 'Profit & Loss'],
  ['/reports/finance/accounts-receivable', 'Accounts Receivable'],
  ['/reports/finance/accounts-payable', 'Accounts Payable'],
  ['/reports/finance/general-ledger', 'General Ledger'],
  ['/reports/finance/balance-sheet', 'Balance Sheet'],
  ['/reports/operations/service-orders', 'Service Order Register'],
  ['/reports/operations/containers', 'Containers'],
] as const

for (const [url, title] of REPORTS) {
  test(`report renders: ${title}`, async ({ page }) => {
    const errors: string[] = []
    page.on('console', message => {
      if (message.type() === 'error') errors.push(message.text())
    })

    await page.goto(url)
    await expect(page.locator('h1')).toContainText(title)
    await expect(page.getByRole('alert').filter({ hasText: /error|failed|denied/i })).toHaveCount(0)

    // Ignore the pre-login refresh call and the CSP-blocked avatar URL.
    expect(errors.filter(text => !/auth\/refresh|ui-avatars/.test(text))).toEqual([])
  })
}
