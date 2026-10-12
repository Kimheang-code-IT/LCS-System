import type { Ref } from 'vue'
import type { FreightRecord } from '~/types/record'
import type { useLcs } from '~/composables/freight/useLcs'
import type { useConfirm } from '~/composables/common/useConfirm'
import { quotationDomainStatus } from '~/utils/freight/states'

type LcsApi = ReturnType<typeof useLcs>

export function useQuotationCommands(options: {
  lcs: LcsApi
  model: Ref<FreightRecord>
  store: ReturnType<typeof useFreightStore>
  confirm: ReturnType<typeof useConfirm>['confirm']
  toast: ReturnType<typeof useToast>['add']
  t: (key: string, ...args: unknown[]) => string
  quotationDraftDirty: Ref<boolean>
  relatedServiceOrder: () => FreightRecord | null | undefined
}) {
  const { lcs, model, store, confirm, toast, t, quotationDraftDirty, relatedServiceOrder } = options

  // Revision-level endpoints (send/submit/accept/convert) require the revision
  // id, not the quotation id. Fall back to the quotation id only when the
  // revision id is unavailable.
  const revisionId = () => String(model.value.revisionId || model.value.id || '')

  function guardSaved(): boolean {
    if (quotationDraftDirty.value) {
      toast({ title: t('freight.ui.missingRequired'), description: t('freight.ui.quotationSaveBeforeSubmit'), color: 'warning' })
      return false
    }
    return true
  }

  async function send() {
    if (quotationDomainStatus(model.value.status) !== 'DRAFT' || !guardSaved()) return
    const ok = await confirm({
      kind: 'submit',
      title: t('freight.ui.quotationSendTitle'),
      description: t('freight.ui.quotationSendDescription'),
      confirmLabel: t('freight.ui.send'),
    })
    if (!ok) return
    const saved = await lcs.runCommand('quotation.send', revisionId(), keyValue =>
      lcs.quotations.send(revisionId(), keyValue),
    )
    model.value = saved
    store.reload()
    toast({ title: t('freight.ui.quotationSent'), color: 'success' })
  }

  async function submit() {
    return send()
  }

  async function accept() {
    if (quotationDomainStatus(model.value.status) !== 'SENT') return
    const ok = await confirm({
      kind: 'submit',
      title: t('freight.ui.quotationAcceptTitle'),
      description: t('freight.ui.quotationAcceptDescription'),
      confirmLabel: t('freight.ui.accept'),
      confirmColor: 'primary',
    })
    if (!ok) return
    const saved = await lcs.runCommand('quotation.accept', revisionId(), keyValue =>
      lcs.quotations.accept(revisionId(), keyValue),
    )
    model.value = saved
    store.reload()
    toast({ title: t('freight.ui.quotationAccepted'), color: 'success' })
  }

  async function rejectOrCancel(key: 'reject' | 'cancel') {
    const nextStatus = key === 'reject' ? 'Rejected' : 'Cancelled'
    model.value = store.save('quotations', { ...model.value, status: nextStatus })
    toast({ title: t(key === 'reject' ? 'freight.ui.quotationRejected' : 'freight.ui.quotationCancelled'), color: key === 'reject' ? 'error' : 'warning' })
  }

  /** Re-quotation: clones the latest revision into a new editable draft. */
  async function createRevision() {
    const ok = await confirm({
      kind: 'submit',
      title: t('freight.ui.quotationRequoteTitle'),
      description: t('freight.ui.quotationRequoteDescription'),
      confirmLabel: t('freight.ui.requote'),
    })
    if (!ok) return
    const created = await lcs.quotations.createRevision(String(model.value.id))
    store.reload()
    toast({ title: t('freight.ui.revisionCreated'), color: 'success' })
    await navigateTo(`/quotations/${String(created.id || model.value.id)}`)
    model.value = created
  }

  async function convertJob() {
    const existing = relatedServiceOrder()
    if (existing?.id) {
      await navigateTo(`/service-orders/${String(existing.id)}`)
      return
    }
    if (!guardSaved()) return
    if (quotationDomainStatus(model.value.status) !== 'ACCEPTED') {
      toast({ title: t('freight.ui.convertRequiresAccepted'), color: 'warning' })
      return
    }
    const ok = await confirm({
      kind: 'submit',
      title: t('freight.ui.quotationConvertTitle'),
      description: t('freight.ui.quotationConvertDescription'),
      confirmLabel: t('freight.ui.convertServiceOrder'),
      confirmColor: 'primary',
    })
    if (!ok) return
    const job = await lcs.runCommand('quotation.convert', revisionId(), keyValue =>
      lcs.quotations.convert(revisionId(), keyValue),
    )
    model.value = { ...model.value, ...job }
    store.reload()
    toast({ title: t('freight.ui.convertedToJob'), color: 'success' })
    await navigateTo(`/service-orders/${String(job.serviceOrderId || job.id)}`)
  }

  return {
    send,
    submit,
    accept,
    rejectOrCancel,
    createRevision,
    convertJob,
  }
}
