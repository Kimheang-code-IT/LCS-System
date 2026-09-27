import type { Ref } from 'vue'
import type { FreightRecord } from '~/types/freight/record'
import type { useLcs } from '~/composables/lcs/useLcs'
import type { useConfirm } from '~/composables/common/useConfirm'
import { canConvertQuotation } from '~/utils/lcs/states'

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

  async function send() {
    const saved = await lcs.runCommand('quotation.send', revisionId(), keyValue =>
      lcs.quotations.send(revisionId(), keyValue),
    )
    model.value = saved
    toast({ title: t('freight.ui.quotationSent'), color: 'success' })
  }

  async function submit() {
    if (quotationDraftDirty.value) {
      toast({ title: t('freight.ui.missingRequired'), description: t('freight.ui.quotationSaveBeforeSubmit'), color: 'warning' })
      return
    }
    const ok = await confirm({
      kind: 'submit',
      title: t('freight.ui.quotationSubmitTitle'),
      description: t('freight.ui.quotationSubmitDescription'),
      confirmLabel: t('freight.ui.quotationSubmit'),
    })
    if (!ok) return
    const saved = await lcs.runCommand('quotation.submit', revisionId(), keyValue =>
      lcs.quotations.submit(revisionId(), keyValue),
    )
    model.value = saved
    store.reload()
    toast({ title: t('freight.ui.quotationSubmitted'), color: 'success' })
  }

  async function accept() {
    const saved = await lcs.runCommand('quotation.accept', revisionId(), keyValue =>
      lcs.quotations.accept(revisionId(), keyValue),
    )
    model.value = saved
    toast({ title: t('freight.ui.quotationAccepted'), color: 'success' })
  }

  async function rejectOrCancel(key: 'reject' | 'cancel') {
    const nextStatus = key === 'reject' ? 'Rejected' : 'Cancelled'
    model.value = store.save('quotations', { ...model.value, status: nextStatus })
    toast({ title: t(key === 'reject' ? 'freight.ui.quotationRejected' : 'freight.ui.quotationCancelled'), color: key === 'reject' ? 'error' : 'warning' })
  }

  async function createRevision() {
    const created = await lcs.quotations.createRevision(String(model.value.id))
    store.reload()
    toast({ title: t('freight.ui.revisionCreated'), color: 'success' })
    await navigateTo(`/quotations/${created.id}`)
  }

  async function convertJob() {
    const existing = relatedServiceOrder()
    if (existing?.id) {
      await navigateTo(`/service-orders/${String(existing.id)}`)
      return
    }
    if (!canConvertQuotation(model.value.status)) {
      toast({ title: t('freight.ui.convertRequiresAccepted'), color: 'warning' })
      return
    }
    const job = await lcs.runCommand('quotation.convert', revisionId(), keyValue =>
      lcs.quotations.convert(revisionId(), keyValue),
    )
    toast({ title: t('freight.ui.convertedToJob'), color: 'success' })
    await navigateTo(`/service-orders/${job.id}`)
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
