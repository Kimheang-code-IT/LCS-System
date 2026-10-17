/**
 * Single source of truth for the UI languages the application ships with.
 *
 * Every other language-aware site (preferences store, format service, App Config
 * localization settings, Nuxt UI locale map) must derive from this list instead
 * of hardcoding a `'en' | 'km'` union, so adding a language is a one-line change
 * plus a locale bundle in `i18n/locales/`.
 *
 * Mirrors `SUPPORTED_LANGUAGES` / `_LANGUAGE_LOCALES` in
 * `backend/app/core/localization.py`, which validates the persisted settings.
 */

export const APP_LANGUAGES = [
  { code: 'en', name: 'English', locale: 'en-US' },
  { code: 'km', name: 'ភាសាខ្មែរ', locale: 'km-KH' },
  { code: 'zh', name: '中文', locale: 'zh-CN' },
] as const

export type AppLanguageCode = (typeof APP_LANGUAGES)[number]['code']

/** Preferred public alias; `AppLocale` is re-exported from the preferences store. */
export type AppLocale = AppLanguageCode

export const APP_LANGUAGE_CODES = APP_LANGUAGES.map(language => language.code)

/** BCP-47 locale per language, used for date/number/month-name formatting. */
export const APP_LANGUAGE_LOCALES: Record<AppLanguageCode, string> = Object.fromEntries(
  APP_LANGUAGES.map(language => [language.code, language.locale]),
) as Record<AppLanguageCode, string>

export const DEFAULT_APP_LANGUAGE: AppLanguageCode = 'en'

const SUPPORTED = new Set<string>(APP_LANGUAGE_CODES)

export function isAppLanguage(value: unknown): value is AppLanguageCode {
  return typeof value === 'string' && SUPPORTED.has(value)
}

export function normalizeAppLanguage(value: unknown, fallback: AppLanguageCode = DEFAULT_APP_LANGUAGE): AppLanguageCode {
  return isAppLanguage(value) ? value : fallback
}

/** Keeps only supported codes, preserving the caller's order and removing duplicates. */
export function normalizeAppLanguages(value: unknown): AppLanguageCode[] {
  if (!Array.isArray(value)) return []
  return [...new Set(value.filter(isAppLanguage))]
}