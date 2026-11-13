import { expect, type Page, test } from './support/fixtures'

/**
 * Master data: one shared party record serves customer and supplier roles.
 * Creates a customer and a supplier, then proves both are listed with the role.
 *
 * The reference form labels its inputs with placeholders only, so the fields
 * are addressed by placeholder rather than by accessible name.
 */
async function createParty(page: Page, kind: 'Customer' | 'Supplier', name: string) {
  await page.goto('/master-data/business-parties/new')
  const code = `E2E-${kind.toUpperCase()}-${Date.now().toString().slice(-7)}`
  await page.getByPlaceholder('Party Code').fill(code)
  await page.getByPlaceholder('Legal Name').fill(name)
  // Mention-style multi-select: filter, then Enter turns the match into a chip.
  const roles = page.getByPlaceholder('Party Roles')
  await roles.click()
  await roles.fill(kind)
  await page.keyboard.press('Enter')
  await expect(page.getByText(kind, { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^(Create|Save changes)$/ }).click()
  await expect(page).toHaveURL(/\/master-data\/business-parties\/?$/)
  return code
}

test('a customer and a supplier party can be created and listed', async ({ page }) => {
  const stamp = Date.now().toString().slice(-7)
  const customer = await createParty(page, 'Customer', `E2E Customer ${stamp}`)
  const supplier = await createParty(page, 'Supplier', `E2E Supplier ${stamp}`)

  for (const code of [customer, supplier]) {
    await expect(page.getByRole('row').filter({ hasText: code })).toHaveCount(1)
  }
  await expect(page.getByRole('row').filter({ hasText: customer })).toContainText('Customer')
  await expect(page.getByRole('row').filter({ hasText: supplier })).toContainText('Supplier')
})

/** A party without its required fields is refused before it is stored. */
test('a business party requires a code, a legal name and a role', async ({ page }) => {
  await page.goto('/master-data/business-parties/new')
  await page.getByRole('button', { name: /^(Create|Save changes)$/ }).click()
  await expect(page.getByText('Party Code is required.')).toBeVisible()
  await expect(page.getByText('Legal Name is required.')).toBeVisible()
  await expect(page.getByText('Party Roles is required.')).toBeVisible()
})
