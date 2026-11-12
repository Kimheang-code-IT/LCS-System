import { expect, test } from './support/fixtures'
import { pickOption } from './support/helpers'

/**
 * Opening an order from the list must keep the record number in the header.
 * Regression: the leaving list page's watcher claimed the new route's chrome
 * and its unmount cleared the breadcrumb, leaving only "Service Orders".
 */
test('service order opened from the list keeps its number in the header', async ({ page }) => {
  await page.goto('/service-orders')
  const row = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^SO\d{4}-\d{6}$/ }) })
    .first()
  const orderNo = (await row.getByRole('link').first().innerText()).trim()
  await row.getByRole('link').first().click()

  await expect(page).toHaveURL(/\/service-orders\/\d+/)
  await expect(page.locator('h1')).toContainText('Service Orders')
  await expect(page.locator('h1')).toContainText(orderNo)
})

/** Service-order tabs: containers, service charges and the finance summary. */
test('service order: container, service charge and finance summary', async ({ page }) => {
  const containerNo = `E2E${Date.now().toString().slice(-9)}`

  await page.goto('/service-orders')
  const firstRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^SO\d{4}-\d{6}$/ }) })
    .first()
  const href = await firstRow.getByRole('link').first().getAttribute('href')
  expect(href).toMatch(/^\/service-orders\/\d+$/)

  // Containers: add a numbered container and reload to prove it persisted.
  await page.goto(`${href}?section=containers`)
  await page.getByRole('button', { name: 'Add Container' }).click()
  const containerRow = page.getByRole('row')
    .filter({ has: page.getByRole('button', { name: 'Container Type' }) })
    .last()
  await containerRow.getByRole('textbox').first().fill(containerNo)
  await pickOption(page, /^Container Type$/, /40-foot General Purpose/)
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page).toHaveURL(/\/service-orders$/)

  await page.goto(`${href}?section=containers`)
  await expect.poll(async () => page.locator('input').evaluateAll(
    elements => elements.map(element => (element as HTMLInputElement).value),
  )).toContain(containerNo)

  // Service charges: add a charge and confirm it lands in the grid.
  await page.goto(`${href}?section=charges`)
  await page.getByRole('button', { name: 'Add charge' }).click()
  await pickOption(page, /^Fee Type$/, /^Demurrage$/)
  const chargeRow = page.getByRole('row').filter({ hasText: 'Demurrage' })
  await chargeRow.getByRole('spinbutton').nth(0).fill('2')
  await chargeRow.getByRole('spinbutton').nth(1).fill('125')
  await page.getByRole('button', { name: 'Save Charge' }).click()
  await expect(page.getByRole('row').filter({ hasText: 'Demurrage' })).toBeVisible()

  // Finance: the summary counts container payments and service charges.
  await page.goto(`${href}?section=finance`)
  await expect(page.getByText('Finance Summary')).toBeVisible()
  await expect(page.getByText('Total Charges')).toBeVisible()
  await expect(page.getByText('Uncharged Amount')).toBeVisible()
})
