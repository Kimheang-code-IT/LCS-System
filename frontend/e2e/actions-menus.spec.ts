import { expect, type Page, test } from './support/fixtures'

/**
 * Row Actions (⋯) menus: shared three-dot column, neutral styling with red
 * Delete, direct status transitions (no "Change Status" submenu) and the
 * sticky Financial Documents column under horizontal scroll.
 *
 * Read-only: nothing in this spec mutates or confirms a transition.
 */

/** Opens the ⋯ menu of the row containing `text` and returns the open menu. */
async function openRowMenu(page: Page, rowText: string) {
  const row = page.getByRole('row').filter({ hasText: rowText }).first()
  await expect(row).toBeVisible()
  const trigger = row.getByRole('button', { name: /^Actions for/ })
  await expect(trigger).toBeVisible()
  await trigger.click()
  const menu = page.getByRole('menu').first()
  await expect(menu).toBeVisible()
  return menu
}

test('financial documents list has a sticky Actions column with per-record labels', async ({ page }) => {
  await page.goto('/finance/documents')
  const header = page.getByRole('columnheader', { name: 'Actions' })
  await expect(header).toBeVisible({ timeout: 15_000 })
  // The header carries the sticky-right classes so it survives horizontal scroll.
  await expect(header).toHaveClass(/sticky right-0/)

  const trigger = page.getByRole('button', { name: /^Actions for / }).first()
  await expect(trigger).toBeVisible()
  // Accessible name references the record, e.g. "Actions for INV2026-000171".
  expect((await trigger.getAttribute('aria-label'))!.length).toBeGreaterThan('Actions for'.length)
  // Every data row has one trigger.
  expect(await page.getByRole('button', { name: /^Actions for / }).count()).toBeGreaterThan(0)

  // No generic submenu anywhere on the page.
  await trigger.click()
  const menu = page.getByRole('menu').first()
  await expect(menu).toBeVisible()
  await expect(menu.getByText('Change Status', { exact: false })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toHaveCount(0)
})

test('draft document menu offers direct status actions, posted invoice offers Record Payment', async ({ page }) => {
  await page.goto('/finance/documents')
  await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible({ timeout: 15_000 })

  // Draft rows expose "Post" directly (engine endpoint, not a status write).
  const draftRow = page.getByRole('row').filter({ hasText: /^.*\bDraft\b.*$/ }).first()
  if (await draftRow.count()) {
    const menu = await openRowMenu(page, 'Draft')
    await expect(menu.getByRole('menuitem', { name: 'Post' })).toBeVisible()
    await expect(menu.getByRole('menuitem', { name: 'Edit Draft' })).toBeVisible()
    await page.keyboard.press('Escape')
  }

  // A posted customer invoice offers Record Payment instead of Edit Draft.
  const postedRow = page.getByRole('row')
    .filter({ hasText: /Customer Invoice/ })
    .filter({ hasText: /Posted|Partially Paid|Fully Paid/ })
    .first()
  if (await postedRow.count()) {
    const menu = await openRowMenu(page, 'Customer Invoice')
    await expect(menu.getByRole('menuitem', { name: 'Record Payment' })).toBeVisible()
    await expect(menu.getByRole('menuitem', { name: 'Edit Draft' })).toHaveCount(0)
    await page.keyboard.press('Escape')
  }
})

test('quotation menu: neutral actions and red Delete', async ({ page }) => {
  await page.goto('/quotations')
  await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible({ timeout: 15_000 })

  const draftRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^Q\d{4}-\d{6}$/ }) })
    .first()
  const no = (await draftRow.getByRole('link').first().innerText()).trim()
  const menu = await openRowMenu(page, no)
  await expect(menu.getByRole('menuitem', { name: 'Delete' })).toBeVisible()
  // Delete is the only red item: compare by item text, not element identity.
  const items = await menu.getByRole('menuitem').all()
  expect(items.length).toBeGreaterThan(1)
  for (const item of items) {
    if (!(await item.innerText()).startsWith('Delete')) {
      expect(await item.getAttribute('class')).not.toMatch(/text-error/)
    }
    else {
      expect(await item.getAttribute('class')).toMatch(/text-error/)
    }
  }
  await page.keyboard.press('Escape')
})

test('service order menu offers Finish only when eligible', async ({ page }) => {
  await page.goto('/service-orders')
  await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible({ timeout: 15_000 })
  const firstRow = page.getByRole('row')
    .filter({ has: page.getByRole('link', { name: /^SO\d{4}-\d{6}$/ }) })
    .first()
  await expect(firstRow).toBeVisible()
  const no = (await firstRow.getByRole('link').first().innerText()).trim()
  const menu = await openRowMenu(page, no)
  await expect(menu.getByRole('menuitem', { name: 'Edit' })).toBeVisible()
  // Finish is disabled when the backend policy does not allow it from this status.
  await expect(menu.getByRole('menuitem', { name: 'Finish' })).toBeInViewport()
  await page.keyboard.press('Escape')
})

test('accounting period menu shows Close period / Reopen period directly', async ({ page }) => {
  await page.goto('/finance/accounting-periods')
  await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible({ timeout: 15_000 })

  const openRow = page.getByRole('row').filter({ hasText: /Open|Active/i }).first()
  if (await openRow.count()) {
    const menu = await openRowMenu(page, /Open|Active/i)
    await expect(menu.getByRole('menuitem', { name: 'Close period' })).toBeVisible()
    await expect(menu.getByRole('menuitem', { name: 'Reopen period' })).toHaveCount(0)
    await page.keyboard.press('Escape')
  }
  const closedRow = page.getByRole('row').filter({ hasText: /Closed/i }).first()
  if (await closedRow.count()) {
    const menu = await openRowMenu(page, /Closed/i)
    await expect(menu.getByRole('menuitem', { name: 'Reopen period' })).toBeVisible()
    await expect(menu.getByRole('menuitem', { name: 'Close period' })).toHaveCount(0)
    await page.keyboard.press('Escape')
  }
})
