import type { QuotationRevisionStatus } from '~/types/domain'
import { quotationDomainStatus } from '~/utils/freight/states'

export type QuotationPermissionInput = {
  /** `quotation.update_draft` — edit, delete, re-quote. */
  updateDraft: boolean
  /** `quotation.send` — draft -> sent. */
  send: boolean
  /** `quotation.accept` — sent -> accepted. */
  accept: boolean
  /** `quotation.convert` — accepted -> service order. */
  convert: boolean
}

export type QuotationActionAvailability = {
  status: QuotationRevisionStatus
  edit: boolean
  send: boolean
  accept: boolean
  convert: boolean
  revise: boolean
  delete: boolean
  openServiceOrder: boolean
}

/**
 * Single source of truth for quotation action availability. Mirrors the backend
 * rules: only DRAFT is editable, only SENT can be accepted, only ACCEPTED can be
 * converted, and a quotation linked to a service order can never be deleted.
 */
export function quotationActionAvailability(
  status: unknown,
  can: QuotationPermissionInput,
  options: { hasServiceOrder?: boolean } = {},
): QuotationActionAvailability {
  const domain = quotationDomainStatus(status)
  const hasServiceOrder = Boolean(options.hasServiceOrder)
  const draft = domain === 'DRAFT'
  const sent = domain === 'SENT'
  const accepted = domain === 'ACCEPTED'
  const converted = domain === 'CONVERTED' || hasServiceOrder

  return {
    status: domain,
    edit: draft && can.updateDraft,
    send: draft && can.send,
    accept: sent && can.accept,
    convert: accepted && can.convert,
    revise: can.updateDraft,
    delete: can.updateDraft && (draft || sent) && !converted,
    openServiceOrder: converted,
  }
}
