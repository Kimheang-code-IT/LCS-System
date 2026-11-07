/**
 * Period Closing is a config-driven workspace page over the accounting periods
 * collection: the page files stay thin (no page-level header/table code), the
 * module config owns columns/fields/status transitions, and close/reopen are
 * status transitions granted by the backend policy — not list-local actions.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appDir = new URL('../app/', import.meta.url)
const page = readFileSync(fileURLToPath(new URL('pages/finance/period-closing/index.vue', appDir)), 'utf8')
const detail = readFileSync(fileURLToPath(new URL('pages/finance/period-closing/[id].vue', appDir)), 'utf8')
const config = readFileSync(fileURLToPath(new URL('config/lcs-reference-modules.ts', appDir)), 'utf8')

describe('period closing page', () => {
  it('is a thin workspace view with no page-owned header or table code', () => {
    expect(page).toContain('definePageMeta({ titleKey: \'freight.pages.periodClosing\', permission: \'finance.accounting_periods.view\' })')
    expect(page).toContain('<template><FreightWorkspaceView /></template>')
    expect(page).toMatchSnapshot()
  })

  it('routes row detail through the shared module page', () => {
    expect(detail).toContain('<template><FreightModulePage /></template>')
  })

  it('registers a config module on the periods collection with closure control', () => {
    expect(config).toContain("path: '/finance/period-closing'")
    expect(config).toContain("collection: 'accountingPeriods'")
    expect(config).toContain("titleKey: 'freight.pages.periodClosing'")
    // Status close/reopen come from the backend policy; the workspace list
    // must not be tableOnly or readOnly, which would drop the row status menu.
    const start = config.indexOf("path: '/finance/period-closing'")
    const end = config.indexOf('}),', start)
    const closeModule = config.slice(start, end)
    expect(closeModule).not.toContain('tableOnly')
    expect(closeModule).not.toContain('readOnly')
  })
})
