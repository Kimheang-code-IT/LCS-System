import { expect, test } from './support/fixtures'
import { pickOption } from './support/helpers'

/** Finance: draft → posted (balanced journal) → reversed. */
test('financial document: create, post and reverse', async ({ page }) => {
  await page.goto('/finance/documents/new')

  await page.getByRole('button', { name: /^(Create|Save changes)$/ }).click()
  await expect(page.getByText('Customer / Supplier (Business Party) is required.')).toBeVisible()

  await page.getByRole('textbox', { name: 'Document Date*' }).fill('12/11/2026')
  await page.getByRole('textbox', { name: 'Posting Date' }).fill('12/11/2026')
  await pickOption(page, /^Customer \/ Supplier \(Business Party\)\*?$/, /Demo Customer One/)

  await page.getByRole('tab', { name: 'Lines' }).click()
  await page.getByRole('button', { name: 'Add financial line' }).click()
  const lineRow = page.getByRole('row').filter({ hasText: /^\d/ }).last()
  await lineRow.getByRole('textbox').first().fill('E2E freight revenue')
  await lineRow.getByRole('spinbutton').nth(0).fill('1')
  await lineRow.getByRole('spinbutton').nth(1).fill('100')
  await lineRow.getByRole('spinbutton').nth(1).press('Tab')
  await page.getByRole('button', { name: /^(Create|Save changes)$/ }).click()
  await expect(page).toHaveURL(/\/finance\/documents$/)

  // The list may be paginated; the newest invoice is the one just saved.
  const listed = await (await page.context().request.get('/api/v1/financial-documents?page_size=200')).json()
  const invoices = (listed.data.items as Array<{ id: string, documentType: string }>)
    .filter(row => row.documentType === 'CUSTOMER_INVOICE')
    .sort((left, right) => Number(right.id) - Number(left.id))
  const documentId = invoices[0]!.id
  await page.goto(`/finance/documents/${documentId}`)
  await expect(page.getByRole('textbox', { name: 'Document No.*' })).toHaveValue(/^INV/)
  await expect(page.getByRole('button', { name: 'Post' })).toBeVisible()
  await page.getByRole('button', { name: 'Post' }).click()
  await expect(page.getByRole('button', { name: 'Post' })).toHaveCount(0)

  // Reverse with a reason; the reversal journal is created server-side.
  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Reverse' }).click()
  await page.getByRole('textbox', { name: 'Reason*' }).fill('E2E reversal test')
  await page.getByRole('dialog', { name: /reversal reason/i }).getByRole('button', { name: 'Reverse' }).click()
  await expect.poll(async () => {
    const response = await page.context().request.get(`/api/v1/financial-documents/${documentId}`)
    return (await response.json()).data.status
  }).toBe('Reversed')
})
