import { expect, test, type Page } from '@playwright/test'

/**
 * The four operations reports are read-only pages that load and refresh on
 * their own. Read-only like the whole suite: it navigates, filters and counts
 * requests, and never creates data.
 *
 *   E2E_USERNAME=e2e E2E_PASSWORD=... pnpm test:e2e e2e/operations-reports.spec.ts
 */
const username = process.env.E2E_USERNAME
const password = process.env.E2E_PASSWORD

const OPERATIONS_REPORTS = [
  '/reports/operations/service-orders',
  '/reports/operations/service-order-status',
  '/reports/operations/containers',
  '/reports/operations/profitability',
]

const PROFITABILITY_URL = /\/api\/v1\/reports\/(?:service-order-)?profitability/

async function signIn(page: Page) {
  await page.goto('/auth/login')
  await page.locator('input[name="email"]').fill(username!)
  await page.locator('input[type="password"]').fill(password!)
  await page.getByRole('button', { name: 'Login', exact: true }).click()
  await expect(page).not.toHaveURL(/\/auth\/login/)
}

async function loaded(page: Page) {
  // Either data rows or the "no matching rows" empty state mean the report ran.
  await expect(page.locator('[role="status"], table tbody tr').first()).toBeVisible()
  await expect(page.getByText('No report generated yet')).toHaveCount(0)
}

test.describe('operations reports load automatically', () => {
  test.skip(!username || !password, 'Set E2E_USERNAME and E2E_PASSWORD to run the report journeys.')

  for (const route of OPERATIONS_REPORTS) {
    test(`no manual report actions on ${route}`, async ({ page }) => {
      await signIn(page)
      await page.goto(route)
      await loaded(page)
      // Generate / Rebuild do not exist on these pages.
      await expect(page.getByRole('button', { name: 'Generate', exact: true })).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Rebuild', exact: true })).toHaveCount(0)
      // No stale-results banner either: results refresh on their own.
      await expect(page.getByText(/Press Generate to refresh/)).toHaveCount(0)
      // The header refresh stays available.
      await expect(page.getByRole('button', { name: 'Refresh' })).toBeVisible()
    })
  }

  test('the profitability endpoint is requested once per page open, not per filter change', async ({ page }) => {
    await signIn(page)
    const calls: string[] = []
    page.on('request', (request) => {
      if (PROFITABILITY_URL.test(request.url())) calls.push(request.url())
    })
    await page.goto('/reports/operations/profitability')
    await loaded(page)
    expect(calls.length, 'one read-only fetch on open').toBe(1)

    // Filters apply to the loaded rows in the browser: no new request and the
    // stale banner never appears.
    await page.getByPlaceholder(/Search/).first().fill('ZZZNOMATCH')
    await page.waitForTimeout(700)
    expect(calls.length, 'filters recompute client-side').toBe(1)
    await expect(page.getByText(/Press Generate to refresh/)).toHaveCount(0)
    // The narrow search yields the (possibly empty) filtered view without error.
    await expect(page.getByRole('button', { name: 'Generate', exact: true })).toHaveCount(0)
  })

  test('the service order register fetches its store collections once on open', async ({ page }) => {
    await signIn(page)
    const jobCalls: string[] = []
    page.on('request', (request) => {
      // The collection list endpoint itself (with its page_size query), not a
      // per-record fetch, and no report POST.
      if (/\/api\/v1\/service-orders(\?|$)/.test(request.url()) && request.method() === 'GET') {
        jobCalls.push(request.url())
      }
    })
    await page.goto('/reports/operations/service-orders')
    await loaded(page)
    // A page open fetches the register data once (deduplicated store cache).
    expect(jobCalls.length, `store fetch deduped: ${jobCalls.join(' | ')}`).toBeLessThanOrEqual(1)
  })
})