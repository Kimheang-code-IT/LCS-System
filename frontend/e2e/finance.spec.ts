import { expect, test } from './support/fixtures'
import { pickOption } from './support/helpers'

/** Finance: draft → posted (balanced journal) → reversed. */
test('financial document: create, post and reverse', async ({ page }) => {
  await page.goto('/finance/documents/new')

  await page.getByRole('button', { name: 'Save changes' }).click()
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
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page).toHaveURL(/\/finance\/documents$/)

  // Newest draft is the first row.
  const draftRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^INV\d{4}-\d{6}$/ }) })
    .first()
  const documentNo = (await draftRow.getByRole('link').first().innerText()).trim()
  const href = await draftRow.getByRole('link').first().getAttribute('href')
  expect(documentNo).toMatch(/^INV\d{4}-\d{6}$/)

  await page.goto(href!)
  await expect(page.getByText('Draft').first()).toBeVisible()
  await page.getByRole('button', { name: 'Post' }).click()
  await expect(page.getByText('Posted').first()).toBeVisible()

  // Reverse with a reason; the reversal journal is created server-side.
  await page.getByRole('button', { name: 'More actions' }).click()
  await page.getByRole('menuitem', { name: 'Reverse' }).click()
  await page.getByRole('textbox', { name: 'Reason*' }).fill('E2E reversal test')
  await page.getByRole('dialog').getByRole('button').last().click()
  await expect(page.getByText('Reversed').first()).toBeVisible()
})
