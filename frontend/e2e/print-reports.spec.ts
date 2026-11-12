import { expect, test } from './support/fixtures'

/**
 * Print/PDF and cross-module consistency.
 *
 * The print route is what the browser prints to PDF, so rendering it with the
 * document number and party is the testable half; the PDF bytes themselves are
 * produced by the browser.
 */
test('the quotation print view renders the document for PDF output', async ({ page }) => {
  await page.goto('/quotations')
  const row = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^Q\d{4}-\d{6}$/ }) })
    .first()
  const quotationNo = (await row.getByRole('link').first().innerText()).trim()
  const href = await row.getByRole('link').first().getAttribute('href')
  const id = href!.split('/').pop()

  await page.goto(`/print/quotations/${id}`)
  await expect(page.locator('body')).toContainText(quotationNo)
  await expect(page.getByRole('button', { name: 'Print' }).first()).toBeVisible()
})

test('the trial balance stays balanced across the ledger reports', async ({ page }) => {
  await page.goto('/reports/finance/trial-balance')

  const rows = page.locator('table tbody tr')
  await expect(rows.first()).toBeVisible()

  const totals = await page.locator('table').first().evaluate((table) => {
    const headers = [...table.querySelectorAll('thead th')]
      .map(cell => (cell.textContent || '').trim().toLowerCase())
    const indexOf = (label: string) => headers.findIndex(header => header.includes(label))
    const columns = {
      periodDebit: indexOf('period debit'),
      periodCredit: indexOf('period credit'),
      closingDebit: indexOf('closing debit'),
      closingCredit: indexOf('closing credit'),
    }
    const sums = { periodDebit: 0, periodCredit: 0, closingDebit: 0, closingCredit: 0 }
    for (const row of table.querySelectorAll('tbody tr')) {
      const cells = [...row.querySelectorAll('td')].map(cell => (cell.textContent || '').trim())
      const amount = (index: number) => {
        if (index < 0 || !cells[index]) return 0
        return Number(cells[index].replace(/[^0-9.-]/g, '')) || 0
      }
      sums.periodDebit += amount(columns.periodDebit)
      sums.periodCredit += amount(columns.periodCredit)
      sums.closingDebit += amount(columns.closingDebit)
      sums.closingCredit += amount(columns.closingCredit)
    }
    return sums
  })

  expect(totals.periodDebit).toBeCloseTo(totals.periodCredit, 2)
  expect(totals.closingDebit).toBeCloseTo(totals.closingCredit, 2)
})
