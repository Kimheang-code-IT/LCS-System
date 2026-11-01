import type { QuotationRevisionStatus } from '~/types/domain'
import { quotationDomainStatus } from '~/utils/freight/states'

export type QuotationPermissionInput = {
  /** `quotation.update_draft` — edit, delete, re-quote. */
  updateDraft: boolean
  /** `quotation.submit` — draft -> submitted (the active workflow step). */
  submit: boolean
  /** `quotation.convert` — submitted (or legacy sent/accepted) -> service order. */
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
 * Single source of truth for quotation action availability. The active workflow
 * is DRAFT -> SUBMITTED -> CONVERTED with a re-quote on every step; SENT and
 * ACCEPTED are legacy statuses that stay convertible but offer no action of
 * their own, and a quotation linked to a service order can never be deleted.
 */
export function quotationActionAvailability(
  status: unknown,
  can: QuotationPermissionInput,
  options: { hasServiceOrder?: boolean } = {},
): QuotationActionAvailability {
  const domain = quotationDomainStatus(status)
  const hasServiceOrder = Boolean(options.hasServiceOrder)
  const draft = domain === 'DRAFT'
  const legacySent = domain === 'SENT'
  const legacyAccepted = domain === 'ACCEPTED'
  const converted = domain === 'CONVERTED' || hasServiceOrder

  return {
    status: domain,
    edit: draft && can.updateDraft,
    submit: draft && can.submit,
    convert: !converted && (domain === 'SUBMITTED' || legacySent || legacyAccepted) && can.convert,
    revise: can.updateDraft,
    // A submitted offer is a formal commitment like a sent one was: withdrawal
    // is a cancel, so deletion stays limited to drafts and legacy sent rows.
    delete: can.updateDraft && (draft || legacySent) && !converted,
    openServiceOrder: converted,
  }
}

/**
 * Re-quotation from a service order raises a *new* quotation, so it is offered on
 * any saved order to whoever may revise a quotation. It never edits the order.
 */
export function serviceOrderRequotationAvailability(input: {
  isCreate: boolean
  hasRecord: boolean
  canRevise: boolean
}): boolean {
  return input.canRevise && !input.isCreate && input.hasRecord
}
