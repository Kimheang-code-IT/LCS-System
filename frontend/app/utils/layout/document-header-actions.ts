import type { FreightAction } from '~/config/freight-modules'

/** Secondary document actions shown in the header ⋯ menu (ERPNext Menu). */
export const DOCUMENT_OVERFLOW_ACTION_KEYS = new Set([
  'print',
  'reverse',
  'recordPayment',
  'backToServiceCharge',
  'createInvoice',
  'viewInvoice',
  'convertJob',
  'createRevision',
  'reject',
  'cancel',
  'send',
  'accept',
])

export function isDocumentOverflowAction(key: string) {
  return DOCUMENT_OVERFLOW_ACTION_KEYS.has(key)
}

export function splitDocumentHeaderActions(actions: FreightAction[]) {
  const primary: FreightAction[] = []
  const overflow: FreightAction[] = []
  for (const action of actions) {
    if (isDocumentOverflowAction(action.key)) overflow.push(action)
    else primary.push(action)
  }
  return { primary, overflow }
}
