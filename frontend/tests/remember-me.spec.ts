import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { readRememberMe, writeRememberMe } from '../app/utils/auth/remember-me'

function memoryStorage() {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => store.clear(),
  }
}

const appFile = (relativePath: string) => readFileSync(
  fileURLToPath(new URL(`../app/${relativePath}`, import.meta.url)),
  'utf8',
)

describe('remember me preference', () => {
  beforeEach(() => {
    vi.stubGlobal('window', globalThis)
    vi.stubGlobal('localStorage', memoryStorage())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('defaults to disabled when nothing is stored', () => {
    expect(readRememberMe()).toEqual({ enabled: false, email: '' })
  })

  it('stores the email only while remember me is enabled', () => {
    writeRememberMe({ enabled: true, email: 'admin@example.test' })
    expect(readRememberMe()).toEqual({ enabled: true, email: 'admin@example.test' })
  })

  it('clears stored preferences when remember me is disabled', () => {
    writeRememberMe({ enabled: true, email: 'admin@example.test' })
    writeRememberMe({ enabled: false, email: '' })
    expect(readRememberMe()).toEqual({ enabled: false, email: '' })
    expect(localStorage.getItem('login:remember:email')).toBeNull()
    expect(localStorage.getItem('login:remember:enabled')).toBeNull()
  })

  it('does not enable remember me without an email', () => {
    writeRememberMe({ enabled: true, email: '' })
    expect(readRememberMe()).toEqual({ enabled: false, email: '' })
  })
})

describe('login page remember me wiring', () => {
  it('renders the checkbox and forwards the choice to the login request', () => {
    const loginPage = appFile('pages/auth/login.vue')
    expect(loginPage).toContain("name: 'remember'")
    expect(loginPage).toContain("type: 'checkbox'")
    expect(loginPage).toContain('loginWithCredentials(email, password, remember)')
    expect(loginPage).toContain('writeRememberMe({ enabled: remember, email })')

    const useAuth = appFile('composables/auth/useAuth.ts')
    expect(useAuth).toContain('remember_me: rememberMe')
  })
})
