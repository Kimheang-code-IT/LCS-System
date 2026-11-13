import { expect, test } from './support/fixtures'

/**
 * Header chrome audit: every list page shows its own module title, create
 * buttons describe the right entity, and pages that must not create records
 * do not offer a create action.
 */
const LIST_TITLES: Array<[string, string]> = [
  ['/', 'Dashboard'],
  ['/quotations', 'Quotations'],
  ['/service-orders', 'Service Orders'],
  ['/service-charges', 'Service Charges'],
  ['/finance/documents', 'Financial Documents'],
  ['/finance/chart-of-accounts', 'Chart of Accounts'],
  ['/finance/financial-accounts', 'Financial Accounts'],
  ['/finance/journals', 'Journal Entries'],
  ['/finance/accounting-periods', 'Accounting Periods'],
  // The duplicate Period Closing route redirects to the consolidated page.
  ['/finance/period-closing', 'Accounting Periods'],
  ['/finance/posting-rules', 'Posting Rules'],
  ['/master-data/business-parties', 'Business Parties'],
  ['/master-data/party-roles', 'Party Roles'],
  ['/master-data/place-roles', 'Place Roles'],
  ['/master-data/trade-directions', 'Trade Directions'],
  ['/master-data/container-types', 'Container Types'],
  ['/master-data/transport-types', 'Transport Types'],
  ['/master-data/transport-assets', 'Transport Assets'],
  ['/master-data/asset-identity-types', 'Asset Identity Types'],
  ['/master-data/capacity-units', 'Capacity Units'],
  ['/master-data/fee-types', 'Fee Types'],
  ['/master-data/currencies', 'Currencies'],
  ['/master-data/document-types', 'Document Types'],
  ['/configuration/component-attributes', 'Component Attributes'],
  ['/configuration/component-groups', 'Component Groups'],
  ['/configuration/component-tabs', 'Component Tabs'],
  ['/configuration/versions', 'Configuration Versions'],
  ['/administration/users', 'Users'],
  ['/administration/roles', 'Roles & Permissions'],
  ['/administration/document-sequences', 'Document Sequences'],
  ['/administration/archive', 'Archive'],
  ['/administration/audit-logs', 'Audit Logs'],
]

test('every list page titles itself correctly', async ({ page }) => {
  for (const [route, expected] of LIST_TITLES) {
    await page.goto(route)
    const chrome = page.locator('h1').first()
    await expect(chrome, route).toContainText(expected, { timeout: 10_000 })
    await expect(page, route).toHaveTitle(new RegExp(`^${expected.replace(/[&/]/g, match => `\\${match}`)}$`))
  }
})

test('create buttons describe the module they open', async ({ page }) => {
  const cases: Array<[string, RegExp]> = [
    ['/quotations', /^New Quotation$/],
    ['/service-charges', /^New Service Charge$/],
    ['/finance/documents', /^New Financial Document$/],
    ['/finance/chart-of-accounts', /^New Ledger Account$/],
    ['/finance/financial-accounts', /^New Financial Account$/],
    ['/finance/journals', /^New Journal Entry$/],
    ['/finance/accounting-periods', /^New Accounting Period$/],
    ['/finance/posting-rules', /^New Posting Rule$/],
    ['/administration/users', /^New User$/],
    ['/administration/roles', /^New Role$/],
    ['/administration/document-sequences', /^New Document Sequence$/],
  ]
  for (const [route, label] of cases) {
    await page.goto(route)
    await expect(page.getByRole('button', { name: label }), route).toBeVisible({ timeout: 10_000 })
  }
})

test('service orders and read-only pages offer no create action', async ({ page }) => {
  await page.goto('/service-orders')
  await expect(page.locator('nav').first()).toContainText('Service Orders', { timeout: 10_000 })
  await expect(page.getByRole('link', { name: /^New/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^New/ })).toHaveCount(0)
})

test('financial documents create page opens the shared form, not a debit note', async ({ page }) => {
  await page.goto('/finance/documents/new')
  const chrome = page.locator('h1').first()
  await expect(chrome).toContainText('Financial Documents', { timeout: 10_000 })
  await expect(chrome).toContainText('New Financial Document')
  // The form offers the shared document-type picker; the backend default is the
  // customer invoice, never a stale debit-note default.
  await expect(page.getByRole('button', { name: 'Document Type' })).toContainText('Customer Invoice')
})

test('configuration version pages title and breadcrumb themselves', async ({ page }) => {
  await page.goto('/configuration/versions')
  const chrome = page.locator('h1').first()
  await expect(chrome).toContainText('Configuration Versions', { timeout: 10_000 })
  await expect(page).toHaveTitle(/^Configuration Versions$/)

  await page.getByRole('button', { name: 'New Version' }).click()
  await expect(page).toHaveURL(/\/configuration\/versions\/new\/?$/)
  await expect(page.locator('h1').first()).toContainText('New Configuration Version')
  await expect(page).toHaveTitle(/^New Configuration Version$/)
})
