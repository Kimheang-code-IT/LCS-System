import { expect, type Page, test } from './support/fixtures'
import { apiSend } from './support/api'
import { pickOption } from './support/helpers'

/** Fill the shared financial-document form (dates, party, one or more lines). */
async function createDocument(
  page: Page,
  options: {
    documentType: string
    party: RegExp
    lines: Array<{ description: string, quantity: number, price: number }>
  },
) {
  await page.goto('/finance/documents/new')
  await pickOption(page, /^Document Type$/, new RegExp(options.documentType))
  await page.getByRole('textbox', { name: 'Document Date*' }).fill('12/11/2026')
  await page.getByRole('textbox', { name: 'Posting Date' }).fill('12/11/2026')
  await pickOption(page, /^Customer \/ Supplier \(Business Party\)\*?$/, options.party)

  await page.getByRole('tab', { name: 'Lines' }).click()
  for (const line of options.lines) {
    await page.getByRole('button', { name: 'Add financial line' }).click()
    const row = page.getByRole('row').filter({ hasText: /^\d/ }).last()
    await row.getByRole('textbox').first().fill(line.description)
    await row.getByRole('spinbutton').nth(0).fill(String(line.quantity))
    await row.getByRole('spinbutton').nth(1).fill(String(line.price))
    await row.getByRole('spinbutton').nth(1).press('Tab')
  }
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page).toHaveURL(/\/finance\/documents$/)
  const firstRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^(INV|BILL)\d{4}-\d{6}$/ }) })
    .first()
  return {
    no: (await firstRow.getByRole('link').first().innerText()).trim(),
    href: await firstRow.getByRole('link').first().getAttribute('href'),
  }
}

/**
 * Open a document and wait until the form is hydrated (the server-generated
 * number has landed) before acting — a click on a still-hydrating page is lost.
 */
async function openDocument(page: Page, href: string) {
  await page.goto(href)
  await expect(page.getByRole('textbox', { name: 'Document No.*' }))
    .toHaveValue(/^(INV|BILL|REC)\d{4}-\d{6}$/)
}

test('an invoice totals its lines and posts once', async ({ page }) => {
  const { href } = await createDocument(page, {
    documentType: 'Customer Invoice',
    party: /Demo Customer One/,
    lines: [
      { description: 'E2E line A', quantity: 2, price: 75 },
      { description: 'E2E line B', quantity: 1, price: 50 },
    ],
  })

  await openDocument(page, href!)
  await expect(page.getByRole('spinbutton', { name: 'Grand Total' })).toHaveValue('200')
  await page.getByRole('button', { name: 'Post' }).click()
  await expect(page.getByText('Posted', { exact: true }).first()).toBeVisible()

  // A second post is idempotent: it succeeds without changing the document.
  const documentId = href!.split('/').pop()!
  const before = await page.request.get(`/api/v1/financial-documents/${documentId}`)
  const beforeBody = (await before.json()).data
  const again = await apiSend(page.context(), 'post', `/api/v1/financial-documents/${documentId}/post`, {})
  expect(again.ok()).toBe(true)
  const afterBody = (await (await page.request.get(`/api/v1/financial-documents/${documentId}`)).json()).data
  expect(afterBody.status).toBe('Posted')
  expect(afterBody.total).toBe(beforeBody.total)
  expect(afterBody.documentNo).toBe(beforeBody.documentNo)
})

test('a supplier bill posts and reaches accounts payable', async ({ page }) => {
  const { href } = await createDocument(page, {
    documentType: 'Supplier Bill',
    party: /Demo Supplier One/,
    lines: [{ description: 'E2E supplier cost', quantity: 1, price: 120 }],
  })

  await openDocument(page, href!)
  await expect(page.getByRole('spinbutton', { name: 'Grand Total' })).toHaveValue('120')
  await page.getByRole('button', { name: 'Post' }).click()
  await expect(page.getByText('Posted', { exact: true }).first()).toBeVisible()

  await page.goto('/reports/finance/accounts-payable')
  await expect(page.getByText('Demo Supplier One').first()).toBeVisible()
})

/**
 * Partial payment: Record Payment opens a receipt for the invoice's party with
 * the invoice number as its reference (never as its own document number), and
 * the receipt posts for less than the invoice total.
 */
test('a partial receipt posts against an invoice', async ({ page }) => {
  const { href } = await createDocument(page, {
    documentType: 'Customer Invoice',
    party: /Demo Customer One/,
    lines: [{ description: 'E2E receivable', quantity: 1, price: 200 }],
  })

  await openDocument(page, href!)
  await page.getByRole('button', { name: 'Post' }).click()
  await expect(page.getByText('Posted', { exact: true }).first()).toBeVisible()
  const invoiceNo = (await page.locator('h1').innerText()).match(/INV\d{4}-\d{6}/)?.[0] || ''
  expect(invoiceNo).toMatch(/^INV\d{4}-\d{6}$/)

  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Record Payment' }).click()
  await expect(page).toHaveURL(/documentType=CUSTOMER_RECEIPT/)
  await expect(page.getByRole('button', { name: /^Customer \/ Supplier/ }))
    .toContainText('Demo Customer One')
  await expect(page.getByRole('textbox', { name: 'Document No.*' })).toHaveValue('')

  await pickOption(page, /^Payment Method$/, /^Cash$/)
  await pickOption(page, /^Financial Account$/, /Cash on Hand/)
  await page.getByRole('tab', { name: 'Lines' }).click()
  await page.getByRole('button', { name: 'Add financial line' }).click()
  const line = page.getByRole('row').filter({ hasText: /^\d/ }).last()
  await line.getByRole('textbox').first().fill('E2E partial payment')
  await line.getByRole('spinbutton').nth(0).fill('1')
  await line.getByRole('spinbutton').nth(1).fill('80')
  await line.getByRole('spinbutton').nth(1).press('Tab')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page).toHaveURL(/\/finance\/documents$/)

  const receiptRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^REC\d{4}-\d{6}$/ }) })
    .first()
  const receiptNo = (await receiptRow.getByRole('link').first().innerText()).trim()
  const receiptHref = await receiptRow.getByRole('link').first().getAttribute('href')

  await openDocument(page, receiptHref!)
  await page.getByRole('button', { name: 'Post' }).click()
  await expect(page.getByText('Posted', { exact: true }).first()).toBeVisible()

  // Both documents keep their own numbers; the receipt stays a partial amount.
  await page.goto('/finance/documents')
  await expect(page.getByRole('row').filter({ hasText: receiptNo })).toContainText('Posted')
  await expect(page.getByRole('row').filter({ hasText: receiptNo })).toContainText('80.00')
  await expect(page.getByRole('row').filter({ hasText: invoiceNo })).toContainText('200.00')
})
