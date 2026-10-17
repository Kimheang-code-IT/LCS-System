import type { Ref } from 'vue'
import type { FreightRecord } from '~/types/record'
import type { useLcs } from '~/composables/freight/useLcs'
import { asNumber } from '~/composables/freight/useFreight'
import type { TraceLink, TraceLinkKind } from '~/utils/freight/traceability'

type LcsApi = ReturnType<typeof useLcs>

export function useFinanceCommands(options: {
  lcs: LcsApi
  model: Ref<FreightRecord>
  store: ReturnType<typeof useFreightStore>
  toast: ReturnType<typeof useToast>['add']
  t: (key: string, ...args: unknown[]) => string
  periodClosed: Ref<boolean>
  recalculate: () => void
  traceLink: (kind: TraceLinkKind) => TraceLink | null | undefined
  openReverse: () => void
  /**
   * Page-level refusal channel. Business-rule errors (closed period, unbalanced
   * journal) are not validation errors and have no single input to own them, so
   * they surface next to the form instead of in a toast.
   */
  onError: (message: string) => void
}) {
  const {
    lcs,
    model,
    store,
    toast,
    t,
    periodClosed,
    recalculate,
    traceLink,
    openReverse,
    onError,
  } = options

  async function issueCharge() {
    const saved = await lcs.runCommand('charge.issue', String(model.value.id), keyValue =>
      lcs.charges.issue(String(model.value.id), keyValue),
    )
    model.value = saved
    toast({ title: t('freight.ui.chargeIssued'), color: 'success' })
  }

  async function createInvoiceFromCharge() {
    const invoice = await lcs.runCommand('charge.create-invoice', String(model.value.id), keyValue =>
      lcs.charges.createFinanceInvoice(String(model.value.id), keyValue),
    )
    store.reload()
    const refreshed = store.get('jobCharges', String(model.value.id))
    if (refreshed) model.value = refreshed
    toast({ title: t('freight.ui.draftInvoiceCreated'), color: 'success' })
    await navigateTo(`/finance/documents/${invoice.id}`)
  }

  async function viewInvoiceFromCharge() {
    const link = traceLink('financeInvoice')
    if (link) await navigateTo(`${link.path}/${link.id}`)
  }

  async function backToServiceCharge() {
    const link = traceLink('serviceCharge')
    if (link) await navigateTo(`${link.path}/${link.id}`)
  }

  async function postDocument() {
    if (periodClosed.value) {
      onError(t('lcs.finance.periodClosed'))
      return
    }
    const saved = await lcs.runCommand('finance.post', String(model.value.id), keyValue =>
      lcs.finance.post(String(model.value.id), keyValue),
    )
    model.value = saved
    toast({ title: t('freight.ui.documentPosted'), color: 'success' })
  }

  async function postJournal() {
    recalculate()
    const lines = Array.isArray(model.value.lines) ? model.value.lines : []
    if (!lines.length || asNumber(model.value.debitTotal) <= 0 || asNumber(model.value.balanceDifference) !== 0) {
      onError(t('freight.ui.journalUnbalanced'))
      return
    }
    // The posting engine owns this status: it checks the balance and the period,
    // stamps posted_at / posted_by and writes the audit row. A local status
    // write would show POSTED while the server still held a draft.
    const saved = await lcs.runCommand('journal.post', String(model.value.id), keyValue =>
      lcs.finance.postJournal(String(model.value.id), keyValue),
    )
    model.value = saved
    store.reload()
    toast({ title: t('freight.ui.journalPosted'), color: 'success' })
  }

  function reverseDocument() {
    openReverse()
  }

  async function recordPayment() {
    await navigateTo({
      path: '/finance/documents/new',
      query: {
        documentType: 'CUSTOMER_RECEIPT',
        customer: String(model.value.customer || ''),
        jobNo: String(model.value.jobNo || ''),
        debitNoteNo: String(model.value.debitNoteNo || ''),
        amountDue: String(model.value.total || model.value.amount || ''),
      },
    })
  }

  return {
    issueCharge,
    createInvoiceFromCharge,
    viewInvoiceFromCharge,
    backToServiceCharge,
    postDocument,
    postJournal,
    reverseDocument,
    recordPayment,
  }
}
