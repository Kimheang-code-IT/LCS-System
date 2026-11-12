import { expect, test } from './support/fixtures'
import { pickOption } from './support/helpers'

/**
 * Critical commercial path: create a quotation, add a route stop and a pricing
 * line, then convert it into a Service Order. Data is marked "E2E".
 */
test('quotation → route + pricing → convert to service order', async ({ page }) => {
  const description = `E2E quotation ${Date.now()}`

  await page.goto('/quotations/new')

  // Required-field validation blocks the save before anything is sent.
  await page.getByRole('button', { name: /^save$/i }).click()
  await expect(page.getByText('Business Party is required.')).toBeVisible()
  await expect(page.getByText('Trade Direction is required.')).toBeVisible()

  await pickOption(page, /^Business Party\*?$/, /Demo Customer One/)
  await pickOption(page, /^Trade Direction\*?$/, /^Import$/)
  await page.getByRole('textbox', { name: 'Description' }).fill(description)
  await page.getByRole('button', { name: /^save$/i }).click()
  await expect(page).toHaveURL(/\/quotations$/)

  // The newest quotation is the first data row; capture its number and link.
  const firstRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^Q\d{4}-\d{6}$/ }) })
    .first()
  const quotationNo = (await firstRow.getByRole('link').first().innerText()).trim()
  const href = await firstRow.getByRole('link').first().getAttribute('href')
  expect(quotationNo).toMatch(/^Q\d{4}-\d{6}$/)

  // Route: a stop survives the save.
  await page.goto(href!)
  await page.getByRole('tab', { name: 'Route' }).click()
  await page.getByRole('button', { name: 'Add Route' }).click()
  await pickOption(page, /^Place Role$/, /^Origin$/)
  await page.getByRole('row').filter({ hasText: 'Origin' })
    .getByRole('textbox').first().fill('E2E Phnom Penh Port')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page).toHaveURL(/\/quotations$/)

  await page.goto(href!)
  await page.getByRole('tab', { name: 'Route' }).click()
  await expect(
    page.getByRole('row').filter({ hasText: 'Origin' }).getByRole('textbox').first(),
  ).toHaveValue('E2E Phnom Penh Port')

  // Pricing: 2 × 1500 totals 3000.
  await page.getByRole('tab', { name: 'Pricing' }).click()
  await page.getByRole('button', { name: 'Add Pricing Line' }).click()
  await pickOption(page, /^Fee Type$/, /^Ocean Freight$/)
  await pickOption(page, /^Transport Mode/, /^Vessel$/)
  const pricingRow = page.getByRole('row').filter({ hasText: 'Ocean Freight' })
  await pricingRow.getByRole('spinbutton').nth(0).fill('2')
  await pricingRow.getByRole('spinbutton').nth(1).fill('1500')
  await pricingRow.getByRole('spinbutton').nth(1).press('Tab')
  await expect(pricingRow).toContainText('$3,000.00')

  // An incomplete line is refused with a field message.
  await page.getByRole('button', { name: 'Add Pricing Line' }).click()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Transport Mode is required.')).toBeVisible()

  // Remove the empty line so the save can complete.
  await page.getByRole('row').filter({ hasText: 'Transport Mode' }).last()
    .getByRole('button', { name: 'Actions' }).click()
  await page.getByRole('menuitem', { name: 'Delete' }).click()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page).toHaveURL(/\/quotations$/)

  // Convert from the list row menu.
  await page.getByRole('row').filter({ hasText: quotationNo })
    .getByRole('button', { name: 'Actions' }).click()
  await page.getByRole('menuitem', { name: 'Convert to Service Order' }).click()
  await page.getByRole('dialog')
    .getByRole('button', { name: 'Convert to Service Order' }).click()
  await expect(page).toHaveURL(/\/service-orders\/\d+/)
  await expect(page).toHaveTitle(/^SO\d{4}-\d{6}$/)

  // The converted order owns one identity per payment row (D1 regression).
  const orderId = page.url().split('/').pop()
  const response = await page.request.get(`/api/v1/service-orders/${orderId}`)
  expect(response.ok()).toBe(true)
  const payments = (await response.json()).data.containerPayments as Array<{ id: string }>
  expect(payments).toHaveLength(2)
  expect(new Set(payments.map(row => row.id)).size).toBe(2)
})

test('a saved quotation does not reappear as a draft', async ({ page, context }) => {
  const description = `E2E saved draft ${Date.now()}`
  await page.goto('/quotations/new')
  await pickOption(page, /^Business Party\*?$/, /Demo Customer One/)
  await pickOption(page, /^Trade Direction\*?$/, /^Import$/)
  await page.getByRole('textbox', { name: 'Description' }).fill(description)
  await page.getByRole('button', { name: /^save$/i }).click()
  await expect(page).toHaveURL(/\/quotations$/)

  // Reopening the create form (new tab: no beforeunload prompt) must be empty.
  const fresh = await context.newPage()
  await fresh.goto('/quotations/new')
  await expect(fresh.getByRole('textbox', { name: 'Description' })).toHaveValue('')
  await expect(fresh.getByRole('textbox', { name: 'Company (printed name)' })).toHaveValue('')
})

test('an unfinished quotation draft is restored', async ({ page, context }) => {
  const marker = `E2E unfinished ${Date.now()}`
  await page.goto('/quotations/new')
  await page.getByRole('textbox', { name: 'Description' }).fill(marker)
  // Let the debounced draft write land before leaving the form.
  await page.waitForTimeout(1200)

  const reopened = await context.newPage()
  await reopened.goto('/quotations/new')
  await expect(reopened.getByRole('textbox', { name: 'Description' })).toHaveValue(marker)
})
