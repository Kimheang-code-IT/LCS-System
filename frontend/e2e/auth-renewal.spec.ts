import { expect, test, type Page } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

// These tests write ONLY to the explicitly opted-in disposable auth stack.
// Normal smoke runs retain their read-only contract.
test.skip(process.env.LCS_AUTH_E2E_ISOLATED !== '1', 'requires disposable auth database and API')
test.setTimeout(120000)

async function signIn(page: Page) {
  await page.goto('/auth/login')
  await page.locator('input[name="email"]').fill('admin@example.test')
  await page.locator('input[type="password"]').fill('Passw0rd!')
  await page.getByRole('button', { name: 'Login', exact: true }).click()
  await expect(page).not.toHaveURL(/\/auth\/login/)
}

function sessionAction(page: Page, action: 'renewAccess' | 'logout') {
  return page.evaluate(async (method) => {
    type Store = Record<'renewAccess' | 'logout', () => Promise<unknown>>
    const root = document.querySelector('#__nuxt') as unknown as {
      __vue_app__: { config: { globalProperties: { $pinia: { _s: Map<string, Store> } } } }
    }
    return root.__vue_app__.config.globalProperties.$pinia._s.get('auth')![method]()
  }, action)
}

test('silent renewal preserves a Service Order draft, saves it, restores reload, and coordinates tabs', async ({ page, context }) => {
  const api = process.env.LCS_AUTH_E2E_API || 'http://localhost:8008'
  await signIn(page)

  const cookies = await context.cookies()
  expect(cookies.find(c => c.name === 'refresh_token')?.httpOnly).toBe(true)
  expect(cookies.find(c => c.name === 'refresh_token')?.path).toBe('/api/v1')
  const csrf = cookies.find(c => c.name === 'XSRF-TOKEN')!.value
  // Use an existing first-page fixture when rerunning: the current Service
  // Order detail screen reads the loaded list store, not a direct record GET.
  const listed = await context.request.get(`${api}/api/v1/service-orders`)
  let record = (await listed.json()).data.items[0]
  if (!record) {
    const created = await context.request.post(`${api}/api/v1/service-orders`, {
      headers: { 'X-CSRF-Token': csrf },
      data: { customer: 'ABC Manufacturing Co., Ltd.', direction: 'Import', date: '2026-10-24', currency: 'USD' },
    })
    expect(created.ok(), await created.text()).toBeTruthy()
    record = (await created.json()).data
  }
  const persisted = await context.request.get(`${api}/api/v1/service-orders/${record.id}`)
  expect(persisted.ok(), await persisted.text()).toBeTruthy()
  await page.goto(`/service-orders/${record.id}`)
  const remark = page.locator('[data-field-key="operationalRemark"] textarea')
  await expect(remark).toBeVisible()
  await remark.fill('Unsaved work survives access expiry')
  let refreshes = 0
  page.on('request', req => { if (req.url().endsWith('/auth/refresh')) refreshes++ })
  // Corrupt only the short-lived access cookie with a genuinely expired signed
  // token supplied by the isolated test runner; preserve the refresh credential.
  const expired = process.env.LCS_AUTH_E2E_EXPIRED_ACCESS
  expect(expired).toBeTruthy()
  await context.addCookies([{ name: 'access_token', value: expired!, domain: 'localhost', path: '/', httpOnly: true, sameSite: 'Lax' }])
  const saved = page.waitForResponse(response => response.url().includes('/api/v1/service-orders/') && response.request().method() === 'PUT' && response.ok())
  await page.getByRole('button', { name: /^Save changes$/i }).click()
  await saved
  expect(refreshes).toBe(1)
  await expect(page).toHaveURL(/\/service-orders$/)

  await page.goto(`/service-orders/${record.id}`)
  await expect(remark).toHaveValue('Unsaved work survives access expiry')
  await page.reload()
  await expect(remark).toHaveValue('Unsaved work survives access expiry')
  const sibling = await context.newPage()
  await sibling.goto(`/service-orders/${record.id}`)
  await expect(sibling.locator('[data-field-key="operationalRemark"] textarea')).toBeVisible()
  await remark.fill('Draft remains after logout in another tab')
  await sessionAction(sibling, 'logout')
  await expect(page.getByRole('alert').filter({ hasText: 'Your session expired' })).toBeVisible()
  await expect(remark).toHaveValue('Draft remains after logout in another tab')
  await expect(page).toHaveURL(new RegExp(`/service-orders/${record.id}`))
  expect(await page.evaluate(() => localStorage.getItem('lcs-access-token'))).toBeNull()
  expect(await page.evaluate(() => localStorage.getItem('lcs-refresh-token'))).toBeNull()
})

test('two tabs share one rotation and a delayed renewal cannot undo logout', async ({ page, context }) => {
  await signIn(page)
  const sibling = await context.newPage()
  await sibling.goto('/service-orders')
  await expect(sibling.getByRole('button', { name: 'Demo Administrator Demo Administrator' })).toBeVisible()
  let rotations = 0
  context.on('request', req => { if (req.url().endsWith('/auth/refresh')) rotations++ })
  let allowRotation!: () => void
  let firstObserved!: () => void
  const rotationHeld = new Promise<void>(resolve => { allowRotation = resolve })
  const rotationReady = new Promise<void>(resolve => { firstObserved = resolve })
  await page.route('**/api/v1/auth/refresh', async route => {
    firstObserved()
    await rotationHeld
    await route.continue()
  })
  const firstRotation = sessionAction(page, 'renewAccess')
  await rotationReady
  const secondRotation = sessionAction(sibling, 'renewAccess')
  await expect.poll(() => sibling.evaluate(async () => (await navigator.locks.query()).pending?.length || 0)).toBe(1)
  allowRotation()
  const results = await Promise.all([firstRotation, secondRotation])
  expect(results).toEqual(['renewed', 'renewed'])
  expect(rotations).toBe(1)
  await page.unroute('**/api/v1/auth/refresh')

  let release!: () => void
  let observed!: () => void
  const held = new Promise<void>(resolve => { release = resolve })
  const ready = new Promise<void>(resolve => { observed = resolve })
  await page.route('**/api/v1/auth/refresh', async route => {
    const response = await route.fetch()
    observed()
    await held
    await route.fulfill({ response })
  })
  const renewal = sessionAction(page, 'renewAccess')
  await ready
  const logout = sessionAction(page, 'logout')
  release()
  await Promise.all([renewal, logout])
  await expect(page).toHaveURL(/\/auth\/login/)
  await expect(sibling.getByRole('alert').filter({ hasText: 'Your session expired' })).toBeVisible()
  expect((await context.cookies()).some(cookie => cookie.name === 'refresh_token')).toBe(false)
})

test('a failed identity check blocks the current draft until verification recovers', async ({ page, context }) => {
  await signIn(page)
  await page.goto('/service-orders')
  const sibling = await context.newPage()
  await sibling.goto('/service-orders')
  await expect(sibling.getByRole('button', { name: 'Demo Administrator Demo Administrator' })).toBeVisible()
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ code: 'TEMPORARILY_UNAVAILABLE' }) }))
  await sessionAction(sibling, 'renewAccess')
  await expect(page.getByRole('alert').filter({ hasText: 'Authentication could not be renewed' })).toBeVisible()
  const blocked = await page.evaluate(async () => {
    const root = document.querySelector('#__nuxt') as unknown as {
      __vue_app__: { config: { globalProperties: { $pinia: { _s: Map<string, { identityUnverified: boolean }> } } } }
    }
    return root.__vue_app__.config.globalProperties.$pinia._s.get('auth')!.identityUnverified
  })
  expect(blocked).toBe(true)
  await page.unroute('**/api/v1/auth/me')
  await sessionAction(page, 'renewAccess')
  await expect(page.getByRole('alert').filter({ hasText: 'Authentication could not be renewed' })).not.toBeVisible()

  let releaseIdentity!: () => void
  let identityObserved!: () => void
  const identityHeld = new Promise<void>(resolve => { releaseIdentity = resolve })
  const identityReady = new Promise<void>(resolve => { identityObserved = resolve })
  await page.route('**/api/v1/auth/me', async route => {
    const response = await route.fetch()
    identityObserved()
    await identityHeld
    await route.fulfill({ response })
  })
  await sessionAction(sibling, 'renewAccess')
  await identityReady
  const waiting = page.evaluate(async () => {
    const root = document.querySelector('#__nuxt') as unknown as {
      __vue_app__: { config: { globalProperties: { $pinia: { _s: Map<string, { waitForIdentity: () => Promise<void> }> } } } }
    }
    await root.__vue_app__.config.globalProperties.$pinia._s.get('auth')!.waitForIdentity()
    return 'settled'
  })
  await sessionAction(sibling, 'logout')
  releaseIdentity()
  expect(await waiting).toBe('settled')
  await expect(page.getByRole('alert').filter({ hasText: 'Your session expired' })).toBeVisible()
})

test('a genuine idle deadline rejects save and preserves the unsaved Service Order', async ({ page, context }) => {
  const databaseUrl = process.env.LCS_AUTH_E2E_DATABASE_URL
  test.skip(!databaseUrl, 'requires explicitly opted-in disposable PostgreSQL URL')
  const parsed = new URL(databaseUrl!)
  expect(['127.0.0.1', 'localhost']).toContain(parsed.hostname)
  expect(parsed.pathname).toMatch(/(_test|_rehearsal)$/)
  await signIn(page)
  const api = process.env.LCS_AUTH_E2E_API || 'http://localhost:8008'
  const listed = await context.request.get(`${api}/api/v1/service-orders`)
  const record = (await listed.json()).data.items[0]
  await page.goto(`/service-orders/${record.id}`)
  const remark = page.locator('[data-field-key="operationalRemark"] textarea')
  await expect(remark).toBeVisible()
  await remark.fill('Keep this unsaved draft after real session expiry')
  const access = (await context.cookies()).find(c => c.name === 'access_token')!.value
  const sid = String(JSON.parse(Buffer.from(access.split('.')[1]!, 'base64url').toString()).sid)
  const result = spawnSync('uv', ['run', 'python', '-c', `
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    engine = create_async_engine(os.environ['LCS_AUTH_E2E_DATABASE_URL'])
    async with engine.begin() as connection:
        await connection.execute(text("UPDATE user_sessions SET last_activity_at = now() - interval '9 hours' WHERE id = :id"), {'id': int(os.environ['LCS_AUTH_E2E_SESSION_ID'])})
    await engine.dispose()
asyncio.run(main())
`], {
    cwd: fileURLToPath(new URL('../../backend', import.meta.url)),
    env: { ...process.env, LCS_AUTH_E2E_SESSION_ID: sid },
    encoding: 'utf8',
  })
  expect(result.status, 'Disposable session expiry fixture must succeed').toBe(0)
  let refreshes = 0
  page.on('request', req => { if (req.url().endsWith('/auth/refresh')) refreshes++ })
  const refused = page.waitForResponse(response => response.url().includes('/api/v1/service-orders/') && response.request().method() === 'PUT')
  await page.getByRole('button', { name: /^Save changes$/i }).click()
  const response = await refused
  expect(response.status()).toBe(401)
  expect((await response.json()).code).toBe('SESSION_EXPIRED')
  await expect(page.getByRole('alert').filter({ hasText: 'Your session expired' })).toBeVisible()
  await expect(remark).toHaveValue('Keep this unsaved draft after real session expiry')
  await expect(page).toHaveURL(new RegExp(`/service-orders/${record.id}`))
  expect(refreshes).toBe(0)
})
