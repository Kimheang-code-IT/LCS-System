import { expect, test } from '@playwright/test'

/**
 * Character-by-character typing regression.
 *
 * `fill()` sets a value in one shot, so it cannot catch an input that is
 * re-created mid-typing. These tests type key by key and assert the *same DOM
 * element* is still focused, which is what fails when a renderer rebuilds a
 * control (or a cell's render function) while the user is typing.
 *
 * The authenticated cases are skipped unless a dedicated, non-production
 * account is supplied:
 *
 *   E2E_USERNAME=e2e@example.test E2E_PASSWORD=... pnpm test:e2e
 *
 * `E2E_DOCUMENT_URL` (e.g. `/service-charges/42`) points at a Service Charge
 * whose "Fee Lines" grid is editable; the line-table case is skipped without it.
 * The suite is read-only: it types into fields but never saves.
 */
const username = process.env.E2E_USERNAME
const password = process.env.E2E_PASSWORD
const documentUrl = process.env.E2E_DOCUMENT_URL

async function typeCharByChar(page: import('@playwright/test').Page, selector: string, text: string) {
  const input = page.locator(selector).first()
  await input.click()
  for (const character of text) {
    await page.keyboard.type(character)
    const focused = await input.evaluate(element => document.activeElement === element)
    expect(focused, `focus left ${selector} after "${character}"`).toBe(true)
  }
  return input
}

test.describe('continuous typing', () => {
  test('login fields keep focus and the caret while typing', async ({ page }) => {
    await page.goto('/auth/login')
    const email = await typeCharByChar(page, 'input[name="email"]', 'operator')
    await expect(email).toHaveValue('operator')

    // A password field keeps a real text caret; email inputs do not expose one.
    const password = await typeCharByChar(page, 'input[type="password"]', 'secret1')
    await expect(password).toHaveValue('secret1')
    const caret = await password.evaluate((element) => {
      const field = element as HTMLInputElement
      return { start: field.selectionStart, length: field.value.length }
    })
    expect(caret.start).toBe(caret.length)

    // Moving to another field and back must not lose what was typed.
    await email.click()
    await page.keyboard.type('2')
    await expect(email).toHaveValue('operator2')
  })

  test('multi-byte (Khmer) input survives composition commit', async ({ page }) => {
    await page.goto('/auth/login')
    const email = page.locator('input[name="email"]')
    await email.click()
    await page.keyboard.insertText('khmer')
    await page.keyboard.insertText('ខ្មែរ')
    await expect(email).toHaveValue('khmerខ្មែរ')
    expect(await email.evaluate(element => document.activeElement === element)).toBe(true)
  })
})

test.describe('continuous typing (signed in)', () => {
  test.skip(!username || !password, 'Set E2E_USERNAME and E2E_PASSWORD to run the signed-in typing checks.')

  test.beforeEach(async ({ page }) => {
    await page.goto('/auth/login')
    await page.locator('input[name="email"]').fill(username!)
    await page.locator('input[type="password"]').fill(password!)
    await page.getByRole('button', { name: 'Login', exact: true }).click()
    await expect(page).not.toHaveURL(/\/auth\/login/)
  })

  test('a form field and a textarea keep focus while typing', async ({ page }) => {
    await page.goto('/master-data/currencies/new')
    const code = await typeCharByChar(page, 'input[placeholder="Code"]', 'QATEST')
    await expect(code).toHaveValue('QATEST')

    const name = page.locator('textarea').first()
    if (await name.count()) {
      await name.click()
      await page.keyboard.type('Line one')
      await page.keyboard.press('Enter')
      await page.keyboard.type('Line two')
      await expect(name).toHaveValue('Line one\nLine two')
      expect(await name.evaluate(element => document.activeElement === element)).toBe(true)
    }
  })

  test('an editable line-table cell keeps focus while typing', async ({ page }) => {
    test.skip(!documentUrl, 'Set E2E_DOCUMENT_URL to a document with an editable line table.')
    test.setTimeout(120_000)
    await page.goto(documentUrl!)

    const cell = page.locator('table input').first()
    const tabs = page.getByRole('tab')
    await expect(tabs.first()).toBeVisible({ timeout: 30_000 })
    for (let index = 0; index < await tabs.count(); index++) {
      if (await cell.isVisible().catch(() => false)) break
      await tabs.nth(index).click({ timeout: 5_000 }).catch(() => {})
      await page.waitForTimeout(800)
    }
    await expect(cell).toBeVisible()

    await cell.click()
    await page.keyboard.press('Control+End')
    await page.keyboard.type('X')
    await expect(cell).toBeFocused()
    await page.keyboard.type('Y')
    await expect(cell).toBeFocused()
    const value = await cell.inputValue()
    expect(value.endsWith('XY')).toBe(true)
  })
})
