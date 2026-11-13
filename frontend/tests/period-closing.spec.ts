/**
 * Period Closing was consolidated into Accounting Periods. The old routes stay
 * as redirects so bookmarks and deep links keep working, and the sidebar has a
 * single entry point with the same closure control.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appDir = new URL('../app/', import.meta.url)
const page = readFileSync(fileURLToPath(new URL('pages/finance/period-closing/index.vue', appDir)), 'utf8')
const detail = readFileSync(fileURLToPath(new URL('pages/finance/period-closing/[id].vue', appDir)), 'utf8')
const config = readFileSync(fileURLToPath(new URL('config/lcs-reference-modules.ts', appDir)), 'utf8')

describe('period closing routes', () => {
  it('redirects the list to accounting periods', () => {
    expect(page).toContain("navigateTo({ path: '/finance/accounting-periods'")
    expect(page).toContain('freight.pages.accountingPeriods')
  })

  it('redirects a detail deep link to the accounting-period detail page', () => {
    expect(detail).toContain('/finance/accounting-periods/${String(route.params.id)}')
  })

  it('keeps a single period module in the config', () => {
    expect(config).not.toContain("path: '/finance/period-closing'")
    expect(config).toContain("path: '/finance/accounting-periods'")
    expect(config).toContain("collection: 'accountingPeriods'")
  })
})
