import { expect, test } from './support/fixtures'

/**
 * Shared list-table layout: one scroll container, sticky column header, sticky
 * summary footer and fixed pagination. The Actions column (header and ⋯
 * trigger) is centred. Read-only: nothing here mutates data.
 */

async function stickyLayout(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const thead = document.querySelector('thead')
    // The shared wrapper's single scroll container: the nearest ancestor of the
    // table that actually scrolls vertically.
    let root: HTMLElement | null = thead?.parentElement?.parentElement ?? null
    while (root && !/auto|scroll/.test(getComputedStyle(root).overflowY)) root = root.parentElement
    const tfoot = document.querySelector('tfoot')
    const pagination = document.querySelector('nav[aria-label]')
    return {
      rootOverflowY: root ? getComputedStyle(root).overflowY : '',
      rootFound: Boolean(root),
      rootScrollable: root ? root.scrollHeight > root.clientHeight : false,
      theadPosition: thead ? getComputedStyle(thead.querySelector('th') as Element).position : '',
      tfootPosition: tfoot ? getComputedStyle(tfoot).position : '',
      tfootBottom: tfoot ? getComputedStyle(tfoot).bottom : '',
      paginationVisible: Boolean(pagination),
    }
  })
}

test('financial documents: sticky header + footer, fixed pagination', async ({ page }) => {
  await page.goto('/finance/documents')
  await expect(page.locator('tfoot').first()).toBeVisible({ timeout: 15_000 })
  // Wait for the loaded rows: the footer sticks to the scroll container once
  // the table reaches its full height.
  await expect(page.getByRole('button', { name: /^Actions for / }).first()).toBeVisible({ timeout: 15_000 })
  await page.waitForTimeout(300)

  const layout = await stickyLayout(page)
  expect(layout.rootFound).toBeTruthy()
  expect(layout.rootOverflowY).toMatch(/auto|scroll/)
  expect(layout.theadPosition).toBe('sticky')
  expect(layout.tfootPosition).toBe('sticky')
  expect(layout.tfootBottom).toBe('0px')

  // Only the rows scroll: header and footer stay put while the body moves.
  const root = page.locator('.overflow-auto').first()
  const headerCell = page.locator('thead th').first()
  const footer = page.locator('tfoot').first()
  const before = await headerCell.boundingBox()
  const footerBefore = await footer.boundingBox()
  await root.evaluate(el => { el.scrollTop = 220 })
  await page.waitForTimeout(200)
  const after = await headerCell.boundingBox()
  const footerAfter = await footer.boundingBox()
  expect(after!.y).toBeCloseTo(before!.y, 0)
  expect(footerAfter!.y).toBeCloseTo(footerBefore!.y, 0)
  expect(await root.evaluate(el => el.scrollTop)).toBeGreaterThan(0)

  // Pagination stays visible at the bottom of the card (desktop pager).
  const nextPage = page.getByRole('button', { name: 'Next Page' })
  await expect(nextPage).toBeVisible()
  await page.getByRole('button', { name: 'Page 2' }).click()
  await expect(page.getByRole('button', { name: 'Page 2' })).toHaveAttribute('aria-current', 'page')
  await expect(page.locator('tfoot').first()).toBeVisible()
})

test('actions column is centred in header and cells', async ({ page }) => {
  await page.goto('/quotations')
  await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible({ timeout: 15_000 })

  const header = page.getByRole('columnheader', { name: 'Actions' })
  expect(await header.evaluate(el => getComputedStyle(el).textAlign)).toBe('center')

  const trigger = page.getByRole('button', { name: /^Actions for / }).first()
  const cell = trigger.locator('xpath=ancestor::td[1]')
  const [cellBox, triggerBox] = [await cell.boundingBox(), await trigger.boundingBox()]
  const cellCenter = cellBox!.x + cellBox!.width / 2
  const triggerCenter = triggerBox!.x + triggerBox!.width / 2
  expect(Math.abs(cellCenter - triggerCenter)).toBeLessThan(4)
})

test('actions dropdown opens near the bottom of the scrollable table', async ({ page }) => {
  await page.goto('/finance/documents')
  await expect(page.locator('tfoot').first()).toBeVisible({ timeout: 15_000 })
  const root = page.locator('.overflow-auto').first()
  // Scroll to the last rows so the trigger sits near the footer.
  await root.evaluate(el => { el.scrollTop = el.scrollHeight })
  await page.waitForTimeout(150)

  const trigger = page.getByRole('button', { name: /^Actions for / }).last()
  await trigger.click()
  const menu = page.getByRole('menu').first()
  await expect(menu).toBeVisible()
  const box = await menu.boundingBox()
  const viewport = page.viewportSize()!
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1)
  await page.keyboard.press('Escape')
})

test('accounting periods and master data tables keep the shared footer', async ({ page }) => {
  for (const route of ['/finance/accounting-periods', '/master-data/currencies']) {
    await page.goto(route)
    await expect(page.locator('tfoot').first(), route).toBeVisible({ timeout: 15_000 })
    await expect(page.locator('tfoot').first(), route).toContainText(/records|កំណត់ត្រា|条记录/)
    const layout = await stickyLayout(page)
    expect(layout.tfootPosition, route).toBe('sticky')
    expect(layout.paginationVisible, route).toBeTruthy()
  }
})
