import type { QuotationRevisionStatus } from '~/types/domain'
import { quotationDomainStatus } from '~/utils/freight/states'

export type QuotationPermissionInput = {
  /** `quotation.update_draft` — edit and delete authority for quotations. */
  updateDraft: boolean
  /** Legacy fields kept so existing call sites compile; no workflow uses them. */
  submit: boolean
  convert: boolean
}

export type QuotationActionAvailability = {
  status: QuotationRevisionStatus
  edit: boolean
  submit: boolean
  convert: boolean
  revise: boolean
  delete: boolean
  openServiceOrder: boolean
}

/**
 * Single source of truth for quotation action availability. A quotation is a
 * reusable commercial reference: it stays editable under CRUD rules, Submit /
 * Send / Accept / Re-quote are retired from the UI, "Convert to Service Order"
 * opens the shared Service Order form with the quotation preselected (one
 * quotation may produce many orders), and deletion is refused only while a
 * service order still depends on it.
 */
export function quotationActionAvailability(
  status: unknown,
  can: QuotationPermissionInput,
  options: { hasServiceOrder?: boolean } = {},
): QuotationActionAvailability {
  const domain = quotationDomainStatus(status)
  const hasServiceOrder = Boolean(options.hasServiceOrder)

  return {
    status: domain,
    edit: can.updateDraft,
    submit: false,
    // "Convert to Service Order" is offered for every quotation the caller may
    // convert: a quotation is reused unlimited times, so no status or
    // already-converted gate applies.
    convert: can.convert,
    revise: false,
    delete: can.updateDraft && !hasServiceOrder,
    openServiceOrder: hasServiceOrder,
  }
}

/**
 * Re-quotation is retired; kept as an always-false helper so old call sites
 * compile unchanged.
 */
export function serviceOrderRequotationAvailability(_input: {
  isCreate: boolean
  hasRecord: boolean
  canRevise: boolean
}): boolean {
  return false
}