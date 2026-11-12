import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { getFreightModule } from '../app/config/freight-modules'

const APP = fileURLToPath(new URL('../app', import.meta.url))
const newPage = readFileSync(`${APP}/pages/service-orders/new.vue`, 'utf8')

const orders = getFreightModule('/service-orders')!

describe('service order creation comes from a quotation only', () => {
  it('offers no manual New Service Order action on the list', () => {
    expect(orders.canCreate).toBe(false)
  })

  it('sends the retired creation route to the quotations list with guidance', () => {
    expect(newPage).toContain("navigateTo('/quotations'")
    expect(newPage).toContain('freight.ui.serviceOrderNeedsQuotation')
    expect(newPage).not.toContain('FreightModulePage')
  })

  it('keeps the source quotation visible but never editable', () => {
    const quotation = orders.fields.find(field => field.key === 'quotationId')
    expect(quotation?.readOnly).toBe(true)
    expect(quotation?.type).toBe('select')
    // Another quotation can never be selected on an existing order.
    expect(quotation?.required).toBeFalsy()
  })
})
