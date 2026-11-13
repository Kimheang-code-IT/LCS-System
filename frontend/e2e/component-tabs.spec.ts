import { expect, test } from './support/fixtures'
import { apiSend } from './support/api'
import type { APIResponse, Page } from '@playwright/test'

/**
 * Service Order dynamic tabs come only from the published configuration.
 *
 * The tests share one database and run in order (`describe.serial`): they build
 * a draft, publish it, edit the draft, publish again, and check that every
 * Service Order keeps rendering the version it was captured under. Configuration
 * is created through the real administration APIs; the assertions are made in
 * the browser. Use an isolated database — publishing here creates versions.
 */
const stamp = Date.now().toString().slice(-7)
const CODES = {
  tab: `e2e_tab_${stamp}`,
  group: `e2e_group_${stamp}`,
  attribute: `e2e_field_${stamp}`,
}
const TAB_NAME = `E2E Published Tab ${stamp}`
const TAB_NAME_V2 = `E2E Published Tab ${stamp} v2`
const FIELD_LABEL = `E2E Published Field ${stamp}`
const FIELD_LABEL_V2 = `E2E Published Field ${stamp} v2`

let tabId = ''
let groupId = ''
let attributeId = ''
let directionId = ''
let attributeCode = ''
let tabCode = ''
let pinnedOrderId = ''

async function json<T = Record<string, unknown>>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()).data as T
}

async function importDirection(page: Page): Promise<string> {
  const response = await page.context().request.get('/api/v1/tradeDirections?page_size=200')
  const rows = await json<{ items: Array<{ id: string, name?: string, code?: string }> }>(response)
  const match = rows.items.find(row => String(row.name || row.code || '').toLowerCase() === 'import')
  expect(match, 'Import trade direction').toBeTruthy()
  return String(match!.id)
}

async function activeVersion(page: Page): Promise<Record<string, unknown> | null> {
  const response = await page.context().request.get('/api/v1/configuration-versions/active')
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()).data as Record<string, unknown> | null
}

async function publish(page: Page, note: string): Promise<APIResponse> {
  return apiSend(page.context(), 'post', '/api/v1/configuration-versions', { changeNote: note })
}

/** A quotation converted to a Service Order, exactly as the UI does it. */
async function newServiceOrder(page: Page): Promise<string> {
  const context = page.context()
  const quotation = await apiSend(context, 'post', '/api/v1/quotations', {
    date: new Date().toISOString().slice(0, 10),
    customer: 'E2E Published Config',
    direction: 'Import',
    currency: 'USD',
    amount: 100,
  })
  const revisionId = String((await json<{ revisionId: string }>(quotation)).revisionId)
  await json(await apiSend(context, 'post', `/api/v1/quotation-revisions/${revisionId}/send`, {}))
  await json(await apiSend(context, 'post', `/api/v1/quotation-revisions/${revisionId}/accept`, {}))
  const converted = await json<{ serviceOrderId: string }>(
    await apiSend(context, 'post', `/api/v1/quotation-revisions/${revisionId}/convert`, {}),
  )
  return String(converted.serviceOrderId)
}

async function openOrder(page: Page, orderId: string) {
  await page.goto(`/service-orders/${orderId}`)
  await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible()
}

async function orderTabs(page: Page, orderId: string): Promise<Array<{ code: string, name: string }>> {
  const response = await page.context().request.get(`/api/v1/service-orders/${orderId}/component-tabs`)
  const data = await json<{ tabs: Array<{ code: string, name: string }> }>(response)
  return data.tabs
}

test.describe.serial('published configuration only', () => {
  test('1. nothing published means no dynamic tabs', async ({ page }) => {
    const active = await activeVersion(page)
    test.skip(active !== null, 'this database already has a published configuration version')

    await page.goto('/configuration/versions')
    await expect(page.getByText(/Live version v\d+/)).toHaveCount(0)

    const orderId = await newServiceOrder(page)
    const tabs = await orderTabs(page, orderId)
    expect(tabs, 'live draft tabs must not reach an operational order').toEqual([])

    await openOrder(page, orderId)
    await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible()
    await expect(page.getByRole('tab', { name: TAB_NAME })).toHaveCount(0)
  })

  test('2. a draft tab stays invisible until it is published', async ({ page }) => {
    directionId = await importDirection(page)

    const createdTab = await json<{ id: string, code: string }>(await apiSend(page.context(), 'post', '/api/v1/component-tabs', {
      code: CODES.tab,
      name: TAB_NAME,
      tradeDirectionId: Number(directionId),
      displayOrder: 10,
    }))
    tabId = String(createdTab.id)
    tabCode = String(createdTab.code)
    groupId = String((await json<{ id: string }>(await apiSend(page.context(), 'post', '/api/v1/component-groups', {
      code: CODES.group,
      name: 'E2E Published Group',
      displayOrder: 10,
    }))).id)
    const createdAttribute = await json<{ id: string, code: string }>(await apiSend(
      page.context(),
      'post',
      '/api/v1/component-attributes',
      { code: CODES.attribute, label: FIELD_LABEL, dataType: 'text' },
    ))
    attributeId = String(createdAttribute.id)
    attributeCode = String(createdAttribute.code)
    await json(await apiSend(
      page.context(),
      'post',
      `/api/v1/component-groups/${groupId}/attributes`,
      { attributeId: Number(attributeId) },
    ))
    await json(await apiSend(
      page.context(),
      'post',
      `/api/v1/component-tabs/${tabId}/groups`,
      { groupId: Number(groupId) },
    ))

    const orderId = await newServiceOrder(page)
    await openOrder(page, orderId)
    await expect(page.getByRole('tab', { name: TAB_NAME })).toHaveCount(0)
    expect((await orderTabs(page, orderId)).map(tab => tab.code)).not.toContain(tabCode)
  })

  test('3. publishing makes the tab, group and field available', async ({ page }) => {
    const published = await publish(page, 'e2e v1')
    expect(published.status(), await published.text()).toBe(201)

    await page.goto('/configuration/versions')
    await expect(page.getByText(/Live version v\d+/)).toBeVisible()

    pinnedOrderId = await newServiceOrder(page)
    await openOrder(page, pinnedOrderId)
    await expect(page.getByRole('tab', { name: TAB_NAME })).toBeVisible()
    await page.getByRole('tab', { name: TAB_NAME }).click()
    await expect(page.getByText(FIELD_LABEL).first()).toBeVisible()
    await expect(page.getByText('E2E Published Group').first()).toBeVisible()
  })

  test('4. editing the draft after publishing does not change the order', async ({ page }) => {
    const renamed = await apiSend(page.context(), 'patch', `/api/v1/component-tabs/${tabId}`, { name: TAB_NAME_V2 })
    expect(renamed.status(), await renamed.text()).toBe(200)

    await openOrder(page, pinnedOrderId)
    await expect(page.getByRole('tab', { name: TAB_NAME })).toBeVisible()
    await expect(page.getByRole('tab', { name: TAB_NAME_V2 })).toHaveCount(0)
  })

  test('5. publishing v2 activates it for new orders only', async ({ page }) => {
    const second = await publish(page, 'e2e v2')
    expect(second.status(), await second.text()).toBe(201)

    const freshOrder = await newServiceOrder(page)
    await openOrder(page, freshOrder)
    await expect(page.getByRole('tab', { name: TAB_NAME_V2 })).toBeVisible()

    // The order captured under v1 keeps its own layout.
    await openOrder(page, pinnedOrderId)
    await expect(page.getByRole('tab', { name: TAB_NAME })).toBeVisible()
    await expect(page.getByRole('tab', { name: TAB_NAME_V2 })).toHaveCount(0)
  })

  test('6. a failed publication keeps the active version', async ({ page }) => {
    const before = await activeVersion(page)
    const emptyTab = await json<{ id: string }>(await apiSend(page.context(), 'post', '/api/v1/component-tabs', {
      code: `e2e_empty_${stamp}`,
      name: 'E2E Empty Tab',
      tradeDirectionId: Number(directionId),
      displayOrder: 99,
    }))

    try {
      const rejected = await publish(page, 'e2e broken')
      expect(rejected.status(), await rejected.text()).toBe(422)
      const body = await rejected.json()
      expect(Object.values(body.field_errors as Record<string, string>).join(' '))
        .toContain('Add at least one group')

      const after = await activeVersion(page)
      expect(String(after?.id)).toBe(String(before?.id))
      expect(after?.status).toBe('PUBLISHED')

      await page.goto('/configuration/versions')
      await expect(page.getByText(/Live version v\d+/)).toBeVisible()
    }
    finally {
      // An empty tab would block every later publish.
      await apiSend(page.context(), 'delete', `/api/v1/component-tabs/${emptyTab.id}`)
    }
  })

  test('7. refresh and navigation keep loading the published layout', async ({ page }) => {
    await openOrder(page, pinnedOrderId)
    await expect(page.getByRole('tab', { name: TAB_NAME })).toBeVisible()

    await page.reload()
    await expect(page.getByRole('tab', { name: TAB_NAME })).toBeVisible()
    await expect(page.getByRole('tab', { name: TAB_NAME_V2 })).toHaveCount(0)

    // Leave the detail page and come back through the list.
    await page.goto('/service-orders')
    const firstRow = page.getByRole('row')
      .filter({ has: page.getByRole('link', { name: /^SO\d{4}-\d{6}$/ }) })
      .first()
    const href = await firstRow.getByRole('link').first().getAttribute('href')
    await firstRow.getByRole('link').first().click()
    await expect(page.getByRole('tab', { name: 'Overview' })).toBeVisible()
    const openedId = href!.split('/').pop()!
    expect((await orderTabs(page, openedId)).map(tab => tab.code)).not.toContain('e2e-empty')
    await expect(page.getByRole('tab', { name: 'E2E Empty Tab' })).toHaveCount(0)
  })

  test('8. saved component values survive a later publish', async ({ page }) => {
    const saved = await apiSend(
      page.context(),
      'post',
      `/api/v1/service-orders/${pinnedOrderId}/component-tabs/groups/${groupId}/rows/bulk`,
      { rows: [{ values: { [attributeCode]: 'E2E saved value' } }] },
    )
    expect(saved.status(), await saved.text()).toBe(200)

    // Draft edit + publish v3 renames the field; the v1 order keeps its schema.
    const relabel = await apiSend(page.context(), 'patch', `/api/v1/component-attributes/${attributeId}`, {
      label: FIELD_LABEL_V2,
    })
    expect(relabel.status(), await relabel.text()).toBe(200)
    expect((await publish(page, 'e2e v3')).status()).toBe(201)

    await openOrder(page, pinnedOrderId)
    await page.getByRole('tab', { name: TAB_NAME }).click()
    await expect(page.getByText(FIELD_LABEL).first()).toBeVisible()
    // The saved value lives in a table cell input.
    await expect.poll(async () => page.locator('input').evaluateAll(
      elements => elements.map(element => (element as HTMLInputElement).value),
    )).toContain('E2E saved value')
    await expect(page.getByText(FIELD_LABEL_V2)).toHaveCount(0)

    // A fresh order follows v3.
    const freshOrder = await newServiceOrder(page)
    await openOrder(page, freshOrder)
    await page.getByRole('tab', { name: TAB_NAME_V2 }).click()
    await expect(page.getByText(FIELD_LABEL_V2).first()).toBeVisible()
  })
})
