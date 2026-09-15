import type { AppConfigLocalization } from '~/types/docetra/settings'
import { useSettingsRepositories } from '~/repositories'
import {
  configureFormats,
  DEFAULT_FORMAT_CONFIG,
  formatCompact,
  formatCurrency,
  formatDate,
  formatDatePart,
  formatDateTime,
  formatMoney,
  formatNumber,
  formatRelativeTime,
  formatTime,
  type RelativeTimeLabels,
} from '~/utils/format/format-service'

export const DEFAULT_APP_LOCALIZATION: AppConfigLocalization = DEFAULT_FORMAT_CONFIG

function syncFormatService(config: AppConfigLocalization) {
  configureFormats(config)
}

/** Single source of truth for App Config localization on every page. */
export function useAppLocalization() {
  const localization = useState<AppConfigLocalization>('app-localization-config', () => ({
    ...DEFAULT_APP_LOCALIZATION,
    availableLanguages: [...DEFAULT_APP_LOCALIZATION.availableLanguages],
  }))
  const loaded = useState('app-localization-loaded', () => false)
  const loading = useState('app-localization-loading', () => false)

  syncFormatService(localization.value)

  watch(localization, (value) => syncFormatService(value), { deep: true })

  async function load(force = false) {
    if (loaded.value && !force) return localization.value
    if (loading.value && !force) {
      await until(loading).toBe(false)
      return localization.value
    }
    loading.value = true
    try {
      const config = await useSettingsRepositories().appConfig.get()
      localization.value = {
        ...DEFAULT_APP_LOCALIZATION,
        ...(config.localization || {}),
        availableLanguages: config.localization?.availableLanguages?.length
          ? [...config.localization.availableLanguages]
          : [...DEFAULT_APP_LOCALIZATION.availableLanguages],
      }
      loaded.value = true
    }
    catch {
      loaded.value = true
    }
    finally {
      loading.value = false
    }
    return localization.value
  }

  function apply(next: Partial<AppConfigLocalization>) {
    localization.value = {
      ...localization.value,
      ...next,
      availableLanguages: next.availableLanguages?.length
        ? [...next.availableLanguages]
        : localization.value.availableLanguages,
    }
    loaded.value = true
  }

  function relativeTime(value: unknown, labels: RelativeTimeLabels, options?: { absoluteAfterDays?: number, fallback?: string }) {
    return formatRelativeTime(value, labels, options)
  }

  onMounted(() => { void load() })

  return {
    localization: readonly(localization),
    loaded: readonly(loaded),
    loading: readonly(loading),
    load,
    apply,
    formatDate,
    formatTime,
    formatDateTime,
    formatDatePart,
    formatNumber,
    formatCurrency,
    formatMoney,
    formatCompact,
    relativeTime,
  }
}
