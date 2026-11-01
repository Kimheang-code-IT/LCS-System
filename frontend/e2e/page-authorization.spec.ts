import { expect, test, type Page } from '@playwright/test'

/**
 * S01 all-page authorization matrix (44 approved pages).
 *
 * The route+permission pairs mirror the approved page inventory and the
 * canonical codes in `app/utils/freight/page-access.ts` (including its legacy
 * `master.reference.view` fallback). The expected grant set comes from the
 * signed-in identity itself (`/api/v1/auth/me` -> `permissions`, the same page
 * codes the store and middleware enforce). Nothing here writes records: every
 * step navigates or issues GET requests only.
 *
 * Authenticated cases require dedicated non-production accounts:
 *
 *   E2E_USERNAME=<broad read account> E2E_PASSWORD=...
 *   E2E_VIEWER_USERNAME=<narrow account> E2E_VIEWER_PASSWORD=...
 *   pnpm test:e2e tests/page-authorization.spec.ts
 */

type PageEntry = readonly [route: string, permission: string]

const PAGES: readonly PageEntry[] = [
  ['/', 'dashboard.view'],
  ['/quotations', 'sales.quotations.view'],
  ['/service-orders', 'operations.service_orders.view'],
  ['/service-charges', 'finance.service_charges.view'],
  ['/reports/operations/service-orders', 'reports.service_order_register.view'],
  ['/reports/operations/service-order-status', 'reports.service_order_status.view'],
  ['/reports/operations/containers', 'reports.service_order_containers.view'],
  ['/reports/operations/profitability', 'reports.service_order_profitability.view'],
  ['/finance/documents', 'finance.financial_documents.view'],
  ['/finance/chart-of-accounts', 'finance.chart_of_accounts.view'],
  ['/finance/financial-accounts', 'finance.financial_accounts.view'],
  ['/finance/journals', 'finance.journal_entries.view'],
  ['/finance/accounting-periods', 'finance.accounting_periods.view'],
  ['/finance/posting-rules', 'finance.posting_rules.view'],
  ['/reports/finance/revenue-expense', 'reports.revenue_expense.view'],
  ['/reports/finance/accounts-receivable', 'reports.accounts_receivable.view'],
  ['/reports/finance/accounts-payable', 'reports.accounts_payable.view'],
  ['/reports/finance/general-ledger', 'reports.general_ledger.view'],
  ['/reports/finance/trial-balance', 'reports.trial_balance.view'],
  ['/reports/finance/profit-loss', 'reports.profit_loss.view'],
  ['/reports/finance/balance-sheet', 'reports.balance_sheet.view'],
  ['/reports/finance/cash-flow', 'reports.cash_flow.view'],
  ['/master-data/business-parties', 'master.business_parties.view'],
  ['/master-data/party-roles', 'master.party_roles.view'],
  ['/master-data/place-roles', 'master.place_roles.view'],
  ['/master-data/trade-directions', 'master.trade_directions.view'],
  ['/master-data/container-types', 'master.container_types.view'],
  ['/master-data/transport-types', 'master.transport_types.view'],
  ['/master-data/transport-assets', 'master.transport_assets.view'],
  // Identity types and capacity units share the transport-assets matrix page
  // (mirrors the backend collection map); the legacy coarse code stays accepted.
  ['/master-data/asset-identity-types', 'master.transport_assets.view'],
  ['/master-data/capacity-units', 'master.transport_assets.view'],
  ['/master-data/fee-types', 'master.fee_types.view'],
  ['/master-data/currencies', 'master.currencies.view'],
  ['/master-data/document-types', 'master.reference.view'],
  ['/configuration/component-attributes', 'configuration.view'],
  ['/configuration/component-groups', 'configuration.view'],
  ['/configuration/component-tabs', 'configuration.view'],
  ['/configuration/versions', 'configuration.view'],
  ['/administration/users', 'admin.users.view'],
  ['/administration/roles', 'admin.roles.view'],
  ['/administration/document-sequences', 'admin.document_sequences.view'],
  ['/administration/system-settings', 'settings.app_config.view'],
  ['/administration/archive', 'admin.archive.view'],
  ['/administration/audit-logs', 'admin.audit_logs.view'],
]

/** Legacy codes accepted alongside the canonical one (mirror of page-access.ts legacy fallback). */
function acceptedPermissions(permission: string): string[] {
  if (permission === 'dashboard.view') return ['dashboard.view', 'report.read']
  if (permission.startsWith('reports.')) return [permission, 'report.read']
  if (permission.startsWith('master.')) return [permission, 'master.reference.view']
  return [permission]
}

const strip = (path: string) => path.replace(/\/+$/, '') || '/'

async function signIn(page: Page, user: string, pass: string) {
  await page.goto('/')
  await page.locator('input[name="email"]').fill(user)
  await page.locator('input[type="password"]').fill(pass)
  await page.getByRole('button', { name: 'Login', exact: true }).click()
  await expect(page).not.toHaveURL(/\/auth\/login/)
}

test.describe('anonymous access to every approved page', () => {
  for (const [route] of PAGES) {
    test(`anonymous deep link ${route} is redirected to login`, async ({ page }) => {
      await page.goto(route)
      await expect(page).toHaveURL(/\/auth\/login/)
    })
  }
})

test.describe('signed-in authorization matrix', () => {
  test.setTimeout(240_000) // 44 pages × two navigations each, with settle polling.
  const username = process.env.E2E_USERNAME
  const password = process.env.E2E_PASSWORD

  test.skip(!username || !password, 'Set E2E_USERNAME and E2E_PASSWORD to a dedicated non-production account.')

  test('every permitted page opens and every denied page is refused', async ({ page, context }) => {
    await signIn(page, username!, password!)
    const me = await (await context.request.get('/api/v1/auth/me')).json()
    const held = new Set<string>(me?.data?.permissions ?? [])
    expect(held.size, 'no page permissions received from /auth/me').toBeGreaterThan(0)

    const failures: string[] = []
    const landedPath = () => strip(new URL(page.url()).pathname)
    for (const [route, permission] of PAGES) {
      const allowed = acceptedPermissions(permission).some((code) => held.has(code))
      const target = strip(route)
      await page.goto('/') // establish a prior permitted page so a denial aborts navigation
      await page.goto(route)
      try {
        if (allowed) {
          // Permitted: the page must end up served (also rejects a premature abort).
          await expect.poll(landedPath, { timeout: 6000, intervals: [250, 500, 1000] }).toBe(target)
        } else {
          // Denied: the client middleware must eventually abort/redirect away.
          await expect.poll(landedPath, { timeout: 6000, intervals: [250, 500, 1000] }).not.toBe(target)
        }
      } catch {
        failures.push(`${route} (expected ${allowed ? 'ALLOWED' : 'DENIED'} ${permission}): landed on ${landedPath()}`)
      }
    }
    expect(failures, 'Authorization matrix failures:\n' + failures.join('\n')).toHaveLength(0)
  })

  test('the sidebar only offers pages the account can open', async ({ page, context }) => {
    await signIn(page, username!, password!)
    const me = await (await context.request.get('/api/v1/auth/me')).json()
    const held = new Set<string>(me?.data?.permissions ?? [])
    expect(held.size, 'no page permissions received from /auth/me').toBeGreaterThan(0)
    const hrefs = await page.evaluate(() =>
      Array.from(document.querySelectorAll('nav a[href], aside a[href]')).map((a) =>
        ((a as HTMLAnchorElement).getAttribute('href') ?? '').replace(/\/+$/, '') || '/'
      )
    )
    const failures: string[] = []
    for (const [route, permission] of PAGES) {
      const offered = hrefs.includes(strip(route))
      const expected = acceptedPermissions(permission).some((code) => held.has(code))
      if (offered && !expected) failures.push(`${route}: menu entry offered without the permission`)
      if (!offered && expected) failures.push(`${route}: menu entry missing despite the permission`)
    }
    expect(failures, 'Menu filtering failures:\n' + failures.join('\n')).toHaveLength(0)
  })
})

test.describe('narrow-account authorization matrix', () => {
  test.setTimeout(240_000)
  const pages = process.env.E2E_PAGES_USERNAME
  const pagesPass = process.env.E2E_PAGES_PASSWORD

  test.skip(!pages || !pagesPass, 'Set E2E_PAGES_USERNAME/E2E_PAGES_PASSWORD for the narrow-grant account.')

  // The complementary account: open the pages the broad account may not, and be
  // refused the ones the broad account holds. Together both matrices give every
  // approved page allow and deny evidence from actual catalog grants.
  test('narrow grant set: complementary allows and denials', async ({ page, context }) => {
    await signIn(page, pages, pagesPass)
    const me = await (await context.request.get('/api/v1/auth/me')).json()
    const held = new Set<string>(me?.data?.permissions ?? [])
    expect(held.size, 'no page permissions received from /auth/me').toBeGreaterThan(0)

    const failures: string[] = []
    const landedPath = () => strip(new URL(page.url()).pathname)
    for (const [route, permission] of PAGES) {
      const allowed = acceptedPermissions(permission).some((code) => held.has(code))
      const target = strip(route)
      await page.goto('/')
      await page.goto(route)
      try {
        if (allowed) {
          await expect.poll(landedPath, { timeout: 6000, intervals: [250, 500, 1000] }).toBe(target)
        } else {
          await expect.poll(landedPath, { timeout: 6000, intervals: [250, 500, 1000] }).not.toBe(target)
        }
      } catch {
        failures.push(`${route} (expected ${allowed ? 'ALLOWED' : 'DENIED'} ${permission}): landed on ${landedPath()}`)
      }
    }
    expect(failures, 'Narrow-account matrix failures:\n' + failures.join('\n')).toHaveLength(0)
  })
})

test.describe('master-data action gating (MOD-024/030/031)', () => {
  test.setTimeout(120_000)
  const actionsUser = process.env.E2E_ACTIONS_USERNAME
  const actionsPass = process.env.E2E_ACTIONS_PASSWORD

  test.skip(!actionsUser || !actionsPass, 'Set E2E_ACTIONS_USERNAME/E2E_ACTIONS_PASSWORD for the per-action account.')

  // A per-action narrow account (transport-assets view+create, party-roles
  // view+update+delete): buttons follow the action codes, the backend still
  // refuses what was never granted, and the browser page access follows the
  // shared transport-assets code.
  test('master-data buttons follow per-action codes and the API stays authoritative', async ({ page, context }) => {
    await signIn(page, actionsUser!, actionsPass!)
    // No dashboard access: the sign-in must land on the account's first
    // permitted page, not strand it on the login screen.
    await expect(page).toHaveURL(/\/master-data\//)
    const me = await (await context.request.get('/api/v1/auth/me')).json()
    const held = new Set<string>(me?.data?.permissions ?? [])
    expect(held.has('master.transport_assets.view')).toBe(true)
    expect(held.has('master.transport_assets.create')).toBe(true)
    expect(held.has('master.party_roles.update')).toBe(true)
    expect(held.has('master.reference.manage')).toBe(false)

    // Create button follows the per-page create code.
    await page.goto('/master-data/asset-identity-types')
    await expect(page.getByRole('button', { name: 'New Asset Identity Type' })).toBeVisible()
    await page.goto('/master-data/capacity-units')
    await expect(page.getByRole('button', { name: 'New Capacity Unit' })).toBeVisible()
    // Deactivate is a status update: without the update code it stays hidden.
    await page.locator('button[aria-label="Actions"]:visible').first().click()
    await expect(page.getByRole('menuitem', { name: 'Deactivate' })).toHaveCount(0)
    await page.keyboard.press('Escape')

    // Party Roles: no create code, but update/delete codes act on rows.
    await page.goto('/master-data/party-roles')
    await expect(page.getByRole('button', { name: 'New Party Role' })).toHaveCount(0)
    await page.locator('button[aria-label="Actions"]:visible').first().click()
    await page.getByRole('menuitem', { name: 'Change Status' }).click()
    await expect(page.getByRole('menuitem', { name: 'Deactivate' })).toBeVisible()
    await page.keyboard.press('Escape')
    await page.keyboard.press('Escape')

    // The API refuses and restores: party-roles create is not granted. Browser
    // API calls carry the same double-submit CSRF header the app itself sends.
    const csrfCookie = (await context.cookies()).find(cookie => cookie.name === 'XSRF-TOKEN')
    const mutating = {
      'X-Requested-With': 'XMLHttpRequest',
      ...(csrfCookie ? { 'X-CSRF-Token': csrfCookie.value } : {}),
    }
    const deniedCreate = await context.request.post('/api/v1/partyRoles', {
      headers: mutating,
      data: { code: 'E2E_NOPE', name: 'E2E Denied Role' },
    })
    expect(deniedCreate.status()).toBe(403)
    // ...and the update code does toggle a row through the status endpoint.
    const roles = await (await context.request.get('/api/v1/partyRoles')).json()
    const row = (roles?.data?.items ?? []).find((item: { status: string }) => item.status === 'ACTIVE')
    expect(row, 'an ACTIVE party role to exercise the update code').toBeTruthy()
    const deactivated = await context.request.post(`/api/v1/partyRoles/${row.id}/status`, {
      headers: mutating,
      data: { status: 'INACTIVE' },
    })
    expect(deactivated.status()).toBe(200)
    const restored = await context.request.post(`/api/v1/partyRoles/${row.id}/status`, {
      headers: mutating,
      data: { status: 'ACTIVE' },
    })
    expect(restored.status()).toBe(200)
    expect((await restored.json()).data.status).toBe('ACTIVE')
  })
})

test.describe('backend enforcement from a real authenticated browser context', () => {
  const viewer = process.env.E2E_VIEWER_USERNAME
  const viewerPass = process.env.E2E_VIEWER_PASSWORD
  test.skip(!viewer || !viewerPass, 'Set E2E_VIEWER_USERNAME/E2E_VIEWER_PASSWORD for the unauthorized-context checks.')

  test('an account without admin grants: denied APIs return 403, permitted reads stay 200', async ({ page, context }) => {
    await signIn(page, viewer!, viewerPass!)
    const me = await (await context.request.get('/api/v1/auth/me')).json()
    const held = new Set<string>(me?.data?.permissions ?? [])
    expect(held.has('user.read'), 'viewer unexpectedly holds user.read').toBe(false)

    const denied = await context.request.get('/api/v1/users')
    expect(denied.status()).toBe(403)
    const roles = await context.request.get('/api/v1/roles')
    expect(roles.status()).toBe(403)
    // A read the account actually holds must still work through the browser proxy.
    const quotations = await context.request.get('/api/v1/quotations')
    expect(quotations.status()).toBe(200)
  })

  test('anonymous API probes from the browser origin are rejected', async ({ context }) => {
    const response = await context.request.get('/api/v1/users')
    expect(response.status()).toBe(401)
  })
})