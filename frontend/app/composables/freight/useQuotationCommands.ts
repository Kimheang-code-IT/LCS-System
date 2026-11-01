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
  /**
   * Page-level refusal channel. "Save the draft first" and "accept before
   * converting" are workflow notices, not validation errors, so they render
   * next to the form instead of as a toast.
   */
  onError: (message: string) => void
}) {
  const { lcs, model, store, confirm, toast, t, quotationDraftDirty, relatedServiceOrder, onError } = options

  // One command in flight at a time: a double-click on Submit/Convert must not
  // queue a second request (the backend guards duplicates; this keeps the UI
  // from even issuing one).
  const busy = ref(false)
  async function run(command: () => Promise<void>) {
    if (busy.value) return
    busy.value = true
    try {
      await command()
    }
    finally {
      busy.value = false
    }
  }

  // Revision-level endpoints (send/submit/accept/convert) require the revision
  // id, not the quotation id. Fall back to the quotation id only when the
  // revision id is unavailable.
  const revisionId = () => String(model.value.revisionId || model.value.id || '')

  function guardSaved(): boolean {
    if (quotationDraftDirty.value) {
      onError(t('freight.ui.quotationSaveBeforeSubmit'))
      return false
    }
    return true
  }

  async function send() {
    return run(async () => {
      if (quotationDomainStatus(model.value.status) !== 'DRAFT' || !guardSaved()) return
      const ok = await confirm({
        kind: 'submit',
        title: t('freight.ui.quotationSubmitTitle'),
        description: t('freight.ui.quotationSubmitDescription'),
        confirmLabel: t('freight.ui.submit'),
      })
      if (!ok) return
      const saved = await lcs.runCommand('quotation.submit', revisionId(), keyValue =>
        lcs.quotations.submit(revisionId(), keyValue),
      )
      model.value = saved
      store.reload()
      toast({ title: t('freight.ui.quotationSubmitted'), color: 'success' })
    })
  }

  async function submit() {
    return send()
  }

  async function accept() {
    return run(async () => {
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
    })
  }

  /** Re-quotation: clones the latest revision into a new editable draft. */
  async function createRevision() {
    return run(async () => {
      if (!guardSaved()) return
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
    })
  }

  async function convertJob() {
    return run(async () => {
      const existing = relatedServiceOrder()
      if (existing?.id) {
        await navigateTo(`/service-orders/${String(existing.id)}`)
        return
      }
      if (!guardSaved()) return
      // The backend decides which statuses convert (SUBMITTED plus the legacy
      // SENT/ACCEPTED); the front end only needs to send a draft away with the
      // "submit first" notice instead of guessing the rest.
      if (quotationDomainStatus(model.value.status) === 'DRAFT') {
        onError(t('freight.ui.convertRequiresAccepted'))
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
    })
  }

  return {
    send,
    submit,
    accept,
    createRevision,
    convertJob,
  }
}
