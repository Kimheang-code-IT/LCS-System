import type { Ref } from 'vue'
import type { FreightModule } from '~/config/freight-modules'
import type { FreightRecord } from '~/types/freight/record'
import type { PrintTemplateId } from '~/config/print-templates'
import { PRINT_SUPPORTED_COLLECTIONS } from '~/config/print-templates'
import { buildPrintRoute } from '~/utils/freight/print-navigation'
import type { useLcs } from '~/composables/lcs/useLcs'
import type { useConfirm } from '~/composables/common/useConfirm'

const NUMBERED_COLLECTIONS = new Set(['quotations', 'jobCharges', 'debitNotes', 'journals'])

export function useDocumentActions(options: {
  module: Ref<FreightModule | undefined>
  model: Ref<FreightRecord>
  store: ReturnType<typeof useFreightStore>
  lcs: ReturnType<typeof useLcs>
  route: ReturnType<typeof useRoute>
  confirm: ReturnType<typeof useConfirm>['confirm']
  toast: ReturnType<typeof useToast>['add']
  t: (key: string, ...args: unknown[]) => string
  canMutateRecord: Ref<boolean>
  deactivationOnly: Ref<boolean>
  printOpen: Ref<boolean>
}) {
  const {
    module,
    model,
    store,
    lcs,
    route,
    confirm,
    toast,
    t,
    canMutateRecord,
    deactivationOnly,
    printOpen,
  } = options

  async function saveViaRepository(collection: string, payload: Record<string, unknown>, isNew: boolean) {
    if (collection === 'quotations') {
      return isNew ? lcs.quotations.create(payload) : lcs.quotations.saveDraft(payload as FreightRecord)
    }
    if (collection === 'jobCharges') {
      return isNew ? lcs.charges.create(payload) : lcs.charges.saveDraft(payload as FreightRecord)
    }
    if (collection === 'debitNotes') {
      return isNew ? lcs.finance.createDocument(payload) : lcs.finance.saveDraft(payload as FreightRecord)
    }
    if (collection === 'journals') {
      return isNew ? lcs.finance.createJournal(payload) : lcs.finance.saveJournal(payload as FreightRecord)
    }
    return null
  }

  async function persistRecord(payload: Record<string, unknown>, isNew: boolean): Promise<FreightRecord | null> {
    if (!module.value) return null
    if (NUMBERED_COLLECTIONS.has(module.value.collection)) {
      const saved = await saveViaRepository(module.value.collection, payload, isNew)
      store.reload()
      return saved
    }
    return isNew
      ? await store.create(module.value.collection, payload, module.value.collection.slice(0, 3))
      : store.save(module.value.collection, payload as FreightRecord)
  }

  async function openPrint(templateId: PrintTemplateId) {
    if (!module.value || !model.value.id) return
    await navigateTo(buildPrintRoute({
      collection: module.value.collection,
      recordId: String(model.value.id),
      template: templateId,
      returnTo: route.fullPath,
      modulePath: module.value.path,
    }))
  }

  function openPrintPicker() {
    if (!module.value || !PRINT_SUPPORTED_COLLECTIONS.includes(module.value.collection)) return
    printOpen.value = true
  }

  async function deleteRecord() {
    if (!module.value || !canMutateRecord.value) return
    const status = String(model.value.status || '').trim().toUpperCase()
    const statusBased = status === 'ACTIVE' || status === 'INACTIVE'
    // Active records (and modules without an active/inactive status) are deactivated, not deleted.
    if (deactivationOnly.value && (!statusBased || status === 'ACTIVE')) {
      model.value = store.save(module.value.collection, {
        ...model.value,
        status: module.value.collection === 'documentSequences' ? 'INACTIVE' : 'Inactive',
      })
      toast({ title: t('freight.ui.recordDeactivated'), color: 'success' })
      return
    }
    const ok = await confirm({ kind: 'delete', count: 1 })
    if (!ok) return
    store.remove(module.value.collection, [String(model.value.id)])
    toast({ title: t('docetra.actions.deletedItems', { n: 1 }), color: 'success' })
    await navigateTo(module.value.path)
  }

  return {
    NUMBERED_COLLECTIONS,
    saveViaRepository,
    persistRecord,
    openPrint,
    openPrintPicker,
    deleteRecord,
  }
}
