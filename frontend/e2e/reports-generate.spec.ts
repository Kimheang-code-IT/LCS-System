import { readFile } from 'node:fs/promises'
import { expect, test, type Page } from '@playwright/test'

/**
 * On-demand financial reports in a real browser.
 *
 * Skipped unless a disposable, non-production test account is supplied:
 *
 *   E2E_USERNAME=e2e E2E_PASSWORD=... E2E_BASE_URL=http://localhost:18080 pnpm test:e2e
 *
 * The suite is read-only: it generates, filters and exports a report. The
 * ledger data it reads is created by the environment fixture (`scripts/e2e-report-data.ps1`),
 * never by this spec.
 */
const username = process.env.E2E_USERNAME
const password = process.env.E2E_PASSWORD

// Trailing slashes: this stack is published on a non-default port, and nginx
// answers a directory without one with an absolute redirect to port 80.
const TRIAL_BALANCE = '/reports/finance/trial-balance/'
const GENERATE_URL = /\/api\/v1\/reports\/trial-balance\/generate/
const EMPTY_TITLE = 'No report generated yet'
const EMPTY_RESULT = 'No matching rows'
const STALE_TEXT = 'Filters changed. Press Generate to refresh these results.'

async function signIn(page: Page) {
  await page.goto('/auth/login/')
  await page.locator('input[name="email"]').fill(username!)
  await page.locator('input[type="password"]').fill(password!)
  await page.getByRole('button', { name: 'Login', exact: true }).click()
  await expect(page).not.toHaveURL(/\/auth\/login/)
}

async function generate(page: Page) {
  await page.getByRole('button', { name: 'Generate', exact: true }).first().click()
}

test.describe('on-demand trial balance', () => {
  test.skip(!username || !password, 'Set E2E_USERNAME and E2E_PASSWORD to run the report journeys.')

  test.beforeEach(async ({ page }) => {
    await signIn(page)
  })

  test('opening the page loads the report automatically', async ({ page }) => {
    const bodies: string[] = []
    page.on('request', (request) => {
      if (GENERATE_URL.test(request.url())) bodies.push(request.postData() || '')
    })

    await page.goto(TRIAL_BALANCE)
    await expect(page.getByText('Totals').first()).toBeVisible()
    await expect(page.getByRole('cell', { name: '1100', exact: true })).toBeVisible()
    expect(bodies.length, 'the report is generated on open').toBeGreaterThan(0)
    expect(JSON.parse(bodies[0]!)).toMatchObject({ page: 1, pageSize: 20 })
    await expect(page.getByText(EMPTY_TITLE)).toHaveCount(0)
  })

  test('a filter change marks the result stale and Reset clears the filters', async ({ page }) => {
    await page.goto(TRIAL_BALANCE)
    await generate(page)
    await expect(page.getByText('Totals').first()).toBeVisible()
    await expect(page.getByText(STALE_TEXT)).toHaveCount(0)

    const accountFrom = page.getByPlaceholder('Account from')
    await accountFrom.fill('1100')
    await expect(page.getByText(STALE_TEXT)).toBeVisible()
    // The rows on screen are kept, but they are labelled as stale.
    await expect(page.getByRole('cell', { name: '1100', exact: true })).toBeVisible()

    await page.getByRole('button', { name: 'Reset filters' }).click()
    await expect(accountFrom).toHaveValue('')
  })

  test('Refresh re-runs the report with the current filters', async ({ page }) => {
    await page.goto(TRIAL_BALANCE)
    await generate(page)
    await expect(page.getByText('Totals').first()).toBeVisible()

    await page.getByPlaceholder('Account from').fill('1100')
    const bodies: string[] = []
    page.on('request', (request) => {
      if (GENERATE_URL.test(request.url())) bodies.push(request.postData() || '')
    })
    await page.getByRole('button', { name: 'Refresh' }).click()

    await expect.poll(() => bodies.length).toBeGreaterThan(0)
    expect(JSON.parse(bodies.at(-1)!)).toMatchObject({ accountFrom: '1100' })
    await expect(page.getByText(STALE_TEXT)).toHaveCount(0)
  })

  test('an empty result shows the generated empty state', async ({ page }) => {
    await page.goto(TRIAL_BALANCE)
    await page.getByPlaceholder('Account from').fill('9999')
    await generate(page)
    await expect(page.getByText(EMPTY_RESULT)).toBeVisible()
    // The control bar stays, so the user can see when the empty report ran.
    await expect(page.getByText('Totals').first()).toBeVisible()
  })

  test('a refused report shows the backend message instead of a blank page', async ({ page }) => {
    await page.route(GENERATE_URL, route => route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        code: 'ACCESS_DENIED',
        message: 'Missing permission: reports.trial_balance.view',
        field_errors: {},
        errors: [],
      }),
    }))

    await page.goto(TRIAL_BALANCE)
    await generate(page)
    await expect(page.getByText('Report failed')).toBeVisible()
    await expect(page.getByText('Missing permission: reports.trial_balance.view')).toBeVisible()
  })

  test('Export downloads the full filtered result, not the visible page', async ({ page }) => {
    await page.goto(TRIAL_BALANCE)
    await generate(page)
    await expect(page.getByText('Totals').first()).toBeVisible()

    // The header menu, not a row's overflow menu.
    await page.getByRole('button', { name: 'More actions' }).first().click()
    await page.getByRole('menuitem', { name: 'Export Data' }).click()
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export', exact: true }).click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toMatch(/^trial-balance-\d{4}-\d{2}-\d{2}\.csv$/)
    const path = await download.path()
    expect(path).toBeTruthy()
    const csv = await readFile(path!, 'utf8')
    expect(csv).toContain('Trial Balance')
    expect(csv).toContain('Account Code')
    expect(csv).toMatch(/\b1100\b/)
    expect(csv).toContain('Totals')
    // The footer reconciles with the screen: both sides of the period agree.
    const totalsRow = csv.split(/\r?\n/).find(line => line.startsWith('Totals'))!
    const cells = totalsRow.split(',')
    expect(Number(cells[5])).toBe(Number(cells[6]))
  })
})

test.describe('on-demand trial balance on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })
  test.skip(!username || !password, 'Set E2E_USERNAME and E2E_PASSWORD to run the report journeys.')

  test('generates, marks stale and resets from the compact toolbar', async ({ page }) => {
    await signIn(page)
    await page.goto(TRIAL_BALANCE)
    // The trial balance auto-loads with its default period; no manual
    // generate is needed before the filter journey below.
    await expect(page.getByText('Totals').first()).toBeVisible()
    await expect(page.getByRole('cell', { name: '1100', exact: true })).toBeVisible()

    // Filters collapse into one popover button below the xl breakpoint.
    await page.getByRole('button', { name: 'Filters' }).click()
    await page.getByPlaceholder('Account from').fill('1100')
    await page.keyboard.press('Escape')
    await expect(page.getByText(STALE_TEXT)).toBeVisible()

    await page.getByRole('button', { name: 'Reset filters' }).click()
    await expect(page.getByText(STALE_TEXT)).toBeVisible()
  })
})
