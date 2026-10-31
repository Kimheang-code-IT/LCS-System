import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { documentActionButtonUi } from '~/utils/layout/document-action-button'

const source = (file: string) =>
  readFileSync(fileURLToPath(new URL(`../app/${file}`, import.meta.url)), 'utf8')

describe('documentActionButtonUi', () => {
  it('primary stays on the New Job design tokens: dark solid', () => {
    expect(documentActionButtonUi('primary')).toEqual({ color: 'neutral', variant: 'solid' })
  })

  it('supporting actions use the solid grey secondary, never outline or transparent', () => {
    for (const color of [undefined, 'neutral', 'success', 'warning', 'secondary'] as const) {
      const ui = documentActionButtonUi(color)
      expect(ui.variant).toBe('solid')
      expect(ui.class).toContain('bg-[#E5E7EB]!')
      expect(ui.class).toContain('text-[#374151]!')
      expect(ui.class).toContain('hover:bg-[#D1D5DB]!')
    }
  })

  it('destructive actions use solid red with white text', () => {
    for (const color of ['error', 'destructive'] as const) {
      const ui = documentActionButtonUi(color)
      expect(ui.variant).toBe('solid')
      expect(ui.class).toContain('bg-[#DC2626]!')
      expect(ui.class).toContain('text-white!')
    }
  })
})

describe('page-header actions share one component and pick the right variant', () => {
  /**
   * Header action buttons render through CommonAppDocumentActionButton, which
   * fixes the New Job geometry (rounded-md, default size, natural width). A raw
   * UButton with one of the header action icons inside the header action block
   * is a drift away from that shared style. Buttons with the same icon
   * elsewhere (row menus, dialogs, table toolbars) are out of scope.
   */
  const rawHeaderAction = (icon: string) =>
    new RegExp(`<UButton[^>]*icon="i-lucide-${icon}"`, 's')

  const headerBlock = (text: string, start: RegExp, end: string) => {
    const from = text.search(start)
    const to = from === -1 ? -1 : text.indexOf(end, from)
    return from === -1 || to === -1 ? text : text.slice(from, to)
  }

  it('the header renders refresh and the overflow trigger as grey secondary', () => {
    const block = headerBlock(
      source('components/layout/AppHeader.vue'),
      /template #right/,
      '</UDashboardNavbar>',
    )
    expect(block).toMatch(/<CommonAppDocumentActionButton[\s\S]*i-lucide-refresh-cw[\s\S]*color="secondary"/)
    expect(block).toMatch(/<CommonAppDocumentActionButton[\s\S]*i-lucide-ellipsis[\s\S]*color="secondary"/)
    expect(block).not.toMatch(rawHeaderAction('refresh-cw'))
    expect(block).not.toMatch(rawHeaderAction('ellipsis'))
  })

  it('refresh rotates only its icon, never the whole button, and skips reduced-motion users', () => {
    const button = source('components/common/AppDocumentActionButton.vue')
    expect(button).toContain('spinIcon')
    expect(button).toContain('motion-safe:animate-spin')
    expect(button).toContain('motion-safe:[animation-duration:800ms]')
    // `loading` still swaps in UButton's spinner for other actions; the refresh
    // pattern keeps the same RefreshCw icon and rotates it instead.
    expect(button.match(/spinIcon \? '' : icon/)).toBeTruthy()

    const header = source('components/layout/AppHeader.vue')
    expect(header).toMatch(/:spin-icon="refreshSpinning"/)
    // The old whole-button spin class is gone; the button itself never animates.
    expect(header).not.toMatch(/'animate-spin' : ''/)
    // Disabled while spinning: rapid clicks cannot queue a duplicate refresh.
    expect(header).toMatch(/:disabled="refreshSpinning"/)
  })

  it('the header spin follows the real request, not a simulated timeout', () => {
    const header = source('components/layout/AppHeader.vue')
    // No artificial wait state at all.
    expect(header).not.toContain('setTimeout')
    // The handler is awaited, so async refreshes hold the spin until they settle…
    expect(header).toMatch(/await handler\(\)/)
    expect(header).toMatch(/finally \{\s*refreshAwaiting\.value = false/)
    // …a rejected refresh can never leave the spin running, and failure
    // feedback stays with the app's real channels (useApi toast / page alerts).
    expect(header).toMatch(/catch \(error\)/)
    expect(header).not.toMatch(/toast\.add/)
    // …and pages that manage their own loading state keep working.
    expect(header).toMatch(/Boolean\(actions\.value\?\.refreshing\) \|\| refreshAwaiting\.value/)
    expect(source('composables/layout/useAppHeader.ts')).toMatch(/onRefresh\?: \(\) => void \| Promise<void>/)
  })

  it('the overflow trigger is labelled More actions', () => {
    expect(source('components/layout/AppHeader.vue')).toMatch(/:aria-label="\$t\('common\.moreActions'\)"/)
  })

  it('the header cancel is the secondary variant too', () => {
    const header = source('components/layout/AppHeader.vue')
    expect(header).toContain('actions?.cancel?.to')
    expect(header).not.toMatch(/<UButton[\s\S]*variant="ghost"[\s\S]*actions\.cancel/)
  })

  it('page header blocks have no raw action UButtons', () => {
    for (const [file, icons] of new Map<string, string[]>([
      ['components/freight/ReportsView.vue', ['play', 'refresh-cw']],
      ['pages/configuration/versions/[id].vue', ['check-circle-2', 'undo-2', 'git-compare', 'trash-2']],
      ['pages/configuration/versions/index.vue', ['upload-cloud']],
      ['components/freight/DocumentView.vue', []],
      ['components/freight/JobDetail.vue', []],
    ])) {
      const text = headerBlock(
        source(file),
        /<LayoutAppHeaderPageActions/,
        '</LayoutAppHeaderPageActions>',
      )
      expect(text, file).toContain('CommonAppDocumentActionButton')
      for (const icon of icons) expect(text, file).not.toMatch(rawHeaderAction(icon))
    }
  })
})
