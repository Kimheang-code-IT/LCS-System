import { expect, test } from './support/fixtures'
import { apiSend } from './support/api'
import type { APIResponse, Page } from '@playwright/test'

/**
 * Payment allocation from the payment document's Allocation tab.
 *
 * Documents are created through the real finance API (posting included) and the
 * allocation itself is driven in the browser, so the preview and the persisted
 * outstanding balance are both covered.
 */
const PARTY = 'Demo Customer One Co., Ltd.'

async function data<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()).data as T
}

async function partyId(page: Page): Promise<string> {
  const response = await page.context().request.get('/api/v1/businessParties?page_size=200')
  const rows = await data<{ items: Array<{ id: string, legalName?: string, displayName?: string }> }>(response)
  const match = rows.items.find(row => String(row.legalName || row.displayName || '') === PARTY)
  expect(match, PARTY).toBeTruthy()
  return String(match!.id)
}

async function createAndPost(page: Page, payload: Record<string, unknown>): Promise<{ id: string, documentNo: string }> {
  const created = await data<{ id: string, documentNo: string }>(
    await apiSend(page.context(), 'post', '/api/v1/financial-documents', payload),
  )
  await data(await apiSend(page.context(), 'post', `/api/v1/financial-documents/${created.id}/post`, {}))
  return created
}

async function openAllocationTab(page: Page, documentId: string) {
  await page.goto(`/finance/documents/${documentId}`)
  await expect(page.getByRole('textbox', { name: 'Document No.*' }))
    .toHaveValue(/^(INV|REC|BILL)/)
  await page.getByRole('tab', { name: 'Allocation' }).click()
}

test('a partial cross-currency receipt applies the converted amount', async ({ page }) => {
  const party = await partyId(page)
  const invoice = await createAndPost(page, {
    documentType: 'CUSTOMER_INVOICE',
    date: '2026-03-01',
    partyId: Number(party),
    currency: 'KHR',
    exchangeRate: 0.00025,
    lines: [{ description: 'Freight', quantity: 1, unitPrice: 4_000_000 }],
  })
  const receipt = await createAndPost(page, {
    documentType: 'CUSTOMER_RECEIPT',
    date: '2026-03-05',
    partyId: Number(party),
    currency: 'USD',
    exchangeRate: 1,
    lines: [{ description: 'Part payment', quantity: 1, unitPrice: 500 }],
  })

  await openAllocationTab(page, receipt.id)
  await page.getByRole('button', { name: 'Allocate' }).click()

  await page.getByRole('dialog').getByRole('combobox', { name: /Related Invoice/ }).click()
  await page.getByRole('option', { name: new RegExp(invoice.documentNo) }).first().click()
  await page.getByRole('spinbutton', { name: /^Amount/ }).fill('500')

  // 500 USD at 1 USD = 4,000 KHR applies 2,000,000 KHR to the invoice.
  await expect(page.getByText('Applied to invoice')).toBeVisible()
  await expect(page.getByText(/2,000,000/).first()).toBeVisible()
  await page.getByRole('dialog').getByRole('button', { name: 'Allocate' }).click()

  // The payment page now lists the allocation and the invoice is half settled.
  await expect(page.getByText(invoice.documentNo).first()).toBeVisible()
  const invoiceAfter = await (await page.context().request.get(`/api/v1/financial-documents/${invoice.id}`)).json()
  expect(invoiceAfter.data.outstanding).toBe(2_000_000)
  await page.goto(`/finance/documents/${invoice.id}`)
  await expect(page.getByRole('spinbutton', { name: 'Grand Total' })).toHaveValue('4,000,000')
})

test('a full allocation clears the outstanding balance', async ({ page }) => {
  const party = await partyId(page)
  const invoice = await createAndPost(page, {
    documentType: 'CUSTOMER_INVOICE',
    date: '2026-03-01',
    partyId: Number(party),
    currency: 'USD',
    exchangeRate: 1,
    lines: [{ description: 'Freight', quantity: 1, unitPrice: 300 }],
  })
  const receipt = await createAndPost(page, {
    documentType: 'CUSTOMER_RECEIPT',
    date: '2026-03-05',
    partyId: Number(party),
    currency: 'USD',
    exchangeRate: 1,
    lines: [{ description: 'Payment', quantity: 1, unitPrice: 300 }],
  })

  await openAllocationTab(page, receipt.id)
  await page.getByRole('button', { name: 'Allocate' }).click()
  await page.getByRole('dialog').getByRole('combobox', { name: /Related Invoice/ }).click()
  await page.getByRole('option', { name: new RegExp(invoice.documentNo) }).first().click()
  await page.getByRole('spinbutton', { name: /^Amount/ }).fill('300')
  await page.getByRole('dialog').getByRole('button', { name: 'Allocate' }).click()

  const invoiceAfter = await (await page.context().request.get(`/api/v1/financial-documents/${invoice.id}`)).json()
  expect(invoiceAfter.data.outstanding).toBe(0)
  await page.goto(`/finance/documents/${invoice.id}`)
  await expect(page.getByRole('spinbutton', { name: 'Grand Total' })).toHaveValue('300')
})

test('a reversed payment offers no allocation action', async ({ page }) => {
  const party = await partyId(page)
  const invoice = await createAndPost(page, {
    documentType: 'CUSTOMER_INVOICE',
    date: '2026-03-01',
    partyId: Number(party),
    currency: 'USD',
    exchangeRate: 1,
    lines: [{ description: 'Freight', quantity: 1, unitPrice: 100 }],
  })
  const receipt = await createAndPost(page, {
    documentType: 'CUSTOMER_RECEIPT',
    date: '2026-03-05',
    partyId: Number(party),
    currency: 'USD',
    exchangeRate: 1,
    lines: [{ description: 'Payment', quantity: 1, unitPrice: 100 }],
  })
  await data(await apiSend(page.context(), 'post', `/api/v1/financial-documents/${receipt.id}/reverse`, {
    reason: 'E2E reversal',
  }))

  await openAllocationTab(page, receipt.id)
  await expect(page.getByRole('button', { name: 'Allocate' })).toHaveCount(0)
  // The invoice remains fully outstanding: the reversed receipt settled nothing.
  const invoiceAfter = await (await page.context().request.get(`/api/v1/financial-documents/${invoice.id}`)).json()
  expect(invoiceAfter.data.outstanding).toBe(100)
  await page.goto(`/finance/documents/${invoice.id}`)
  await expect(page.getByRole('spinbutton', { name: 'Grand Total' })).toHaveValue('100')
})
