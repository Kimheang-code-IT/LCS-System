import { expect, test } from './support/fixtures'
import { apiSend } from './support/api'
import { pickOption } from './support/helpers'
import type { APIResponse, Page } from '@playwright/test'

/**
 * Receive Payment from the Service Order finance tab.
 *
 * A posted customer invoice is created through the real finance API for an
 * existing Service Order; the receipt (create + post + allocation) is driven in
 * the browser, and the persisted invoice outstanding is verified over the API.
 */
const INVOICE_AMOUNT = 300
const PAYMENT_AMOUNT = 200

async function data<T>(response: APIResponse): Promise<T> {
  expect(response.ok(), await response.text()).toBe(true)
  return (await response.json()).data as T
}

async function orderWithCustomer(page: Page): Promise<{ id: string, customer: string, currency: string }> {
  const rows = await data<{ items: Array<Record<string, unknown>> }>(
    await page.context().request.get('/api/v1/service-orders?page_size=50'),
  )
  const order = rows.items.find(row => String(row.customer || '').trim())
  expect(order, 'a service order with a customer').toBeTruthy()
  return {
    id: String(order!.id),
    customer: String(order!.customer),
    currency: String(order!.currency || 'USD'),
  }
}

async function partyIdByName(page: Page, name: string): Promise<string> {
  const rows = await data<{ items: Array<{ id: string, legalName?: string, displayName?: string }> }>(
    await page.context().request.get('/api/v1/businessParties?page_size=200'),
  )
  const match = rows.items.find(row =>
    String(row.legalName || row.displayName || '').trim() === name)
  expect(match, `party ${name}`).toBeTruthy()
  return String(match!.id)
}

test('receive payment creates, posts and allocates a receipt', async ({ page }) => {
  const order = await orderWithCustomer(page)
  const party = await partyIdByName(page, order.customer)
  const invoice = await data<{ id: string, documentNo: string }>(
    await apiSend(page.context(), 'post', '/api/v1/financial-documents', {
      documentType: 'CUSTOMER_INVOICE',
      date: new Date().toISOString().slice(0, 10),
      partyId: Number(party),
      serviceOrderId: Number(order.id),
      currency: order.currency,
      lines: [{ description: 'E2E receive payment invoice', quantity: 1, unitPrice: INVOICE_AMOUNT }],
    }),
  )
  await data(await apiSend(page.context(), 'post', `/api/v1/financial-documents/${invoice.id}/post`, {}))

  await page.goto(`/service-orders/${order.id}?section=finance`)
  // The finance tab's summary cards (the tab is titled "Finance" now).
  await expect(page.getByText('Total Charges')).toBeVisible()

  // The summary counts only the posted invoice, not the drafts around it.
  await expect(page.getByText('Outstanding Receivable')).toBeVisible()
  // The entries table shows date/type/description/status/amount; the row menu
  // owns the document actions (the invoice number is in the document itself).
  const invoiceRow = page.getByRole('row').filter({ hasText: 'E2E receive payment invoice' }).first()
  await expect(invoiceRow).toBeVisible()
  await expect(invoiceRow.getByText('Posted').first()).toBeVisible()

  // Receive Payment from the invoice row menu: the invoice comes preselected.
  await invoiceRow.getByRole('button', { name: /^Actions/ }).click()
  await page.getByRole('menuitem', { name: 'Receive Payment' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()

  await pickOption(page, /^Financial Account/, /.+/)
  await dialog.getByRole('textbox', { name: 'Payment Method' }).fill('Cash')
  await dialog.getByRole('spinbutton', { name: /^Amount/ }).fill(String(PAYMENT_AMOUNT))
  // The preselected invoice starts at its full outstanding; pay partially.
  // The allocation's spinbutton is the only unnamed one (the payment amount is
  // labelled), and it comes after it in the DOM.
  await dialog.getByRole('spinbutton').last().fill(String(PAYMENT_AMOUNT))
  await dialog.getByRole('button', { name: 'Save' }).click()

  // The receipt is created, posted and allocated: the persisted invoice
  // outstanding is authoritative (the UI table shows totals, not balances).
  await expect.poll(async () => {
    const response = await page.context().request.get(`/api/v1/financial-documents/${invoice.id}`)
    return (await response.json()).data.outstanding
  }).toBe(INVOICE_AMOUNT - PAYMENT_AMOUNT)

  // The receipt was created, posted and allocated (verified above through the
  // persisted invoice balance; the payments table is covered by its own specs).
})
