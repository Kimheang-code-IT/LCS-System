import { expect, type Page } from '@playwright/test'

/**
 * Open a select-style combobox and choose an option.
 *
 * Remote option lists re-render while the popover opens, so a single click can
 * land on a detached node; one retry after reopening the list is enough.
 */
export async function pickOption(page: Page, field: RegExp, option: RegExp) {
  const trigger = page.getByRole('button', { name: field })
  const choice = page.getByRole('option', { name: option }).first()
  await trigger.click()
  try {
    await choice.click({ timeout: 4000 })
  }
  catch {
    await trigger.click()
    await choice.click({ timeout: 6000 })
  }
}

/** The pricing/charge grid's numeric cells have no label; address them by row. */
export function lineRow(page: Page, text: RegExp) {
  return page.getByRole('row').filter({ hasText: text })
}

export async function expectNoFieldErrors(page: Page) {
  await expect(page.locator('[aria-invalid="true"]')).toHaveCount(0)
}
