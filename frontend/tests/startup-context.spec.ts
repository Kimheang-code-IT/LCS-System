import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const appFile = (relativePath: string) => readFileSync(
  fileURLToPath(new URL(`../app/${relativePath}`, import.meta.url)),
  'utf8',
)

const executableSource = (source: string) => source
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/\/\/.*$/gm, '')

describe('client startup composition context', () => {
  it('keeps plugin-time dependencies free of component-scoped i18n', () => {
    const startupPlugin = appFile('plugins/01.auth-hydrate.client.ts')
    expect(startupPlugin).toContain('usePreferencesStore()')
    expect(startupPlugin).toContain('useAppLocalization()')

    for (const dependency of [
      'stores/preferences.ts',
      'composables/useApi.ts',
    ]) {
      const source = appFile(dependency)
      expect(executableSource(source), dependency).not.toMatch(/\buseI18n\s*\(/)
      expect(source, dependency).toContain('useNuxtApp()')
    }
  })

  it('does not request protected branding during logged-out startup', () => {
    const source = executableSource(appFile('app.vue'))
    const guard = source.indexOf('if (!auth.isLoggedIn)')
    const request = source.indexOf('appInfo.get()')

    expect(guard).toBeGreaterThan(-1)
    expect(request).toBeGreaterThan(guard)
  })
})
