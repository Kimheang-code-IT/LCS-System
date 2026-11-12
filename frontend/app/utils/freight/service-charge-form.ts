/**
 * Shared Service Charge form model.
 *
 * The standalone `/service-charges` page and the Service Order's Service Charge
 * tab render the same `DocumentAppForm` from the `jobCharges` module config.
 * This module owns the parts both callers must agree on: the tab set, the empty
 * linked charge and the payload sent to the existing charge API.
 */
import type { FreightModule, FreightTable } from '~/config/freight-modules'
import type { DocumentFieldSchema, DocumentTabSchema } from '~/types/common'
import type { FreightRecord } from '~/types/record'
import { getFreightModule } from '~/config/freight-modules'
import { lineTableField, moduleDocumentTabs } from '~/utils/freight/document-tabs'
import { recalculateFreightRecord } from '~/utils/freight/document-calculations'
import { createClientId } from '~/utils/client-id'

export const SERVICE_CHARGE_MODULE_PATH = '/service-charges'
export const SERVICE_CHARGE_DRAFT_COLLECTION = 'serviceOrderCharge'

export function serviceChargeModule(): FreightModule {
  const module = getFreightModule(SERVICE_CHARGE_MODULE_PATH)
  if (!module) throw new Error('Service Charge module is not configured')
  return module
}

/** The approved fee-line columns, with the internal cost/margin pair added. */
export function internalFeeLinesTable(module: FreightModule): FreightTable {
  const base = module.tables?.find(table => table.key === 'feeLines')
  if (!base) throw new Error('Service Charge module has no feeLines table')
  const columns = [...base.columns]
  const unitIndex = columns.findIndex(column => column.key === 'unitAmount')
  columns.splice(unitIndex >= 0 ? unitIndex + 1 : columns.length, 0,
    {
      key: 'costUnitPrice',
      label: 'Cost Unit Price',
      labelKey: 'freight.ui.costUnitPrice',
      type: 'number',
      rule: { number: true, nonNegative: true, decimalPlaces: 4 },
    },
    {
      key: 'costAmount',
      label: 'Cost Amount',
      labelKey: 'freight.ui.costAmount',
      type: 'number',
      computed: true,
    },
    {
      key: 'margin',
      label: 'Margin',
      labelKey: 'freight.ui.margin',
      type: 'number',
      computed: true,
    },
  )
  return {
    ...base,
    columns,
    computeRow: (context) => {
      const computed = base.computeRow?.(context) || {}
      const amount = Number(computed.amount ?? context.row.amount ?? 0)
      const costAmount = Number((Number(context.row.quantity || 0) * Number(context.row.costUnitPrice || 0)).toFixed(2))
      return { ...computed, costAmount, margin: Number((amount - costAmount).toFixed(2)) }
    },
  }
}

function supplierField(): DocumentFieldSchema {
  return {
    key: 'supplierPartyId',
    label: 'Supplier',
    labelKey: 'freight.ui.supplier',
    type: 'select',
    required: true,
  }
}

/** Tabs both hosts render: General + Fee Lines, and Traceability once saved. */
export function serviceChargeFormTabs(
  module: FreightModule,
  record: FreightRecord,
  options: { linkedToOrder?: boolean, feeLinesOnly?: boolean } = {},
): DocumentTabSchema[] {
  const internal = String(record.chargeSide || '').toUpperCase() === 'INTERNAL'
  const tabs = moduleDocumentTabs(module, {
    isCreate: !record.id,
    chargeLinkedToJob: options.linkedToOrder === true,
    chargeManualNumber: false,
    record,
    status: String(record.status || 'Draft'),
  })
  const withInternalLines = internal
    ? tabs.map(tab => tab.id === 'fee-lines'
        ? {
            ...tab,
            sections: [{
              id: 'fee-lines',
              fields: [
                supplierField(),
                lineTableField(internalFeeLinesTable(module), {
                  chargeLinkedToJob: options.linkedToOrder === true,
                }),
              ],
            }],
          }
        : tab)
    : tabs
  if (options.feeLinesOnly) return withInternalLines.filter(tab => tab.id === 'fee-lines')
  return record.id ? withInternalLines : withInternalLines.filter(tab => tab.id !== 'traceability')
}

/** A linked draft charge; nothing is sent until the operator saves it. */
export function emptyLinkedServiceCharge(
  job: Record<string, unknown>,
  options: { clientRowId?: string, chargeSide?: 'CUSTOMER' | 'INTERNAL' } = {},
): FreightRecord {
  const record: FreightRecord = { id: '' }
  for (const field of serviceChargeModule().fields) {
    record[field.key] = field.type === 'number' ? 0 : ''
  }
  return {
    ...record,
    serviceOrderId: String(job.id || ''),
    jobNo: String(job.jobNo || ''),
    customer: String(job.customer || ''),
    customerPartyId: String(job.customerPartyId || ''),
    chargeSide: options.chargeSide || 'CUSTOMER',
    supplierPartyId: '',
    currency: String(job.currency || ''),
    documentType: 'SERVICE_NOTE',
    documentDate: new Date().toISOString().slice(0, 10),
    status: 'Draft',
    // Stable marker: a repeated save/retry adopts this row instead of creating a
    // second charge. It travels in the charge's own API payload.
    clientRowId: options.clientRowId || createClientId('charge'),
    feeLines: [{ feeType: '', description: '', quantity: 1, unitAmount: 0 }],
  }
}

/** The model a save sends: derived totals fresh, empty auto-started lines dropped. */
export function serviceChargeFormPayload(record: FreightRecord): FreightRecord {
  const module = serviceChargeModule()
  const next = recalculateFreightRecord(module, record)
  const lines = Array.isArray(next.feeLines) ? next.feeLines as Array<Record<string, unknown>> : []
  return {
    ...next,
    feeLines: lines.filter(line => Boolean(String(line.description ?? '').trim())
      || Boolean(String(line.feeType ?? '').trim())
      || Number(line.unitAmount ?? line.unitPrice ?? 0) !== 0),
  }
}

/** Draft record id: the order plus the charge (or its client marker while new). */
export function serviceChargeDraftRecordId(orderId: string, record: FreightRecord): string {
  const chargeId = String(record.id || '').trim()
  return chargeId ? `${orderId}:${chargeId}` : `${orderId}:new:${String(record.clientRowId || '')}`
}
