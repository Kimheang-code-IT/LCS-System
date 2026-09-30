import { readonly, ref, watch } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getConfig = vi.fn()

vi.mock('~/repositories', () => ({
  useSettingsRepositories: () => ({ appConfig: { get: getConfig } }),
}))

const state = new Map<string, ReturnType<typeof ref>>()

beforeEach(() => {
  state.clear()
  getConfig.mockReset()
  vi.stubGlobal('useState', (key: string, init: () => unknown) => {
    if (!state.has(key)) state.set(key, ref(init()))
    return state.get(key)
  })
  vi.stubGlobal('readonly', readonly)
  vi.stubGlobal('watch', watch)
  vi.stubGlobal('until', (source: { value: unknown }) => ({
    toBe: async (expected: unknown) => {
      while (source.value !== expected) await Promise.resolve()
    },
  }))
  vi.stubGlobal('useAuthStore', () => ({ isLoggedIn: true }))
})

describe('useAppLocalization', () => {
  it('loads localization once and reuses global state', async () => {
    getConfig.mockResolvedValue({
      localization: {
        defaultLanguage: 'km',
        availableLanguages: ['en', 'km'],
        timezone: 'Asia/Phnom_Penh',
        dateFormat: 'YYYY-MM-DD',
        timeFormat: 'HH:mm',
        firstDayOfWeek: 1,
        numberFormat: '#,##0.00',
        currency: 'KHR',
        locale: 'km-KH',
      },
    })
    const { useAppLocalization } = await import('../app/composables/settings/useAppLocalization')
    const first = useAppLocalization()
    const second = useAppLocalization()
    await Promise.all([first.load(), second.load()])
    expect(getConfig).toHaveBeenCalledTimes(1)
    expect(first.localization.value.currency).toBe('KHR')
    expect(second.localization.value.dateFormat).toBe('YYYY-MM-DD')
  })

  it('keeps safe fallback values when the API is unavailable', async () => {
    getConfig.mockRejectedValue(new Error('offline'))
    const { useAppLocalization, DEFAULT_APP_LOCALIZATION } = await import('../app/composables/settings/useAppLocalization')
    const localization = useAppLocalization()
    await localization.load()
    expect(localization.localization.value).toEqual(DEFAULT_APP_LOCALIZATION)
    expect(localization.loaded.value).toBe(false)
  })

  it('applies a saved setting immediately', async () => {
    const { useAppLocalization } = await import('../app/composables/settings/useAppLocalization')
    const localization = useAppLocalization()
    localization.apply({ dateFormat: 'MM/DD/YYYY', currency: 'EUR' })
    expect(localization.formatDate('2026-10-01')).toBe('10/01/2026')
    expect(localization.formatMoney(1250)).toMatch(/1,250\.00/)
    expect(localization.localization.value.currency).toBe('EUR')
  })
})
