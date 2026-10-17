import type { DropdownMenuItem } from '@nuxt/ui'
import type { Ref } from 'vue'
import type { FreightModule } from '~/config/freight-modules'
import type { RecordStatusPolicy, RecordStatusTransition } from '~/types/status'
import { useModuleRepository } from '~/repositories'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePrompt } from '~/composables/common/usePrompt'
import { useLcs } from '~/composables/freight/useLcs'
import { statusActionMeta, statusTransitionsFor, statusValueOf } from '~/utils/freight/status-actions'
import { statusCommand } from '~/utils/freight/status-commands'

/** Policies are static per collection; one fetch per page load is enough. */
const policyCache = new Map<string, RecordStatusPolicy>()
/** Collections the backend has no status policy for (reports, audit logs…). */
const missingPolicies = new Set<string>()

export interface UseRecordStatusOptions {
  /** A refused transition is reported where the user can see the record. */
  onError?: (message: string) => void
  /** Called after a successful change, once the store has been refreshed. */
  onChanged?: () => void | Promise<void>
}

/** Per-run extras a screen can add without owning the status logic. */
export interface StatusRunExtras {
  /** Replaces the generic confirm description (e.g. the period closing check). */
  confirmDescription?: (transition: RecordStatusTransition) => string | undefined
  /** Hides a transition a screen knows is not applicable to this record. */
  allowTransition?: (transition: RecordStatusTransition) => boolean
}

/**
 * The reusable status manager for one module.
 *
 * It renders only the transitions the backend says are legal from the record's
 * current status *and* that this caller may perform, runs them through the path
 * that owns them (the shared status endpoint for plain statuses, the document's
 * own workflow endpoint for posting, reversal, issuing and closing), asks for
 * confirmation — and a reason where one is required — and reports the outcome.
 *
 * Used by the list row menu and the record's "..." menu, so both offer exactly
 * the same actions.
 */
export function useRecordStatus(
  module: Ref<FreightModule | undefined>,
  options: UseRecordStatusOptions = {},
) {
  const { t } = useI18n()
  const { confirm } = useConfirm()
  const { prompt } = usePrompt()
  const toast = useToast()
  const lcs = useLcs()
  const store = useFreightStore()

  const policy = ref<RecordStatusPolicy | null>(null)
  const busyId = ref('')

  async function loadPolicy(force = false) {
    const current = module.value
    if (!current) {
      policy.value = null
      return
    }
    if (!force && policyCache.has(current.collection)) {
      policy.value = policyCache.get(current.collection)!
      return
    }
    if (!force && missingPolicies.has(current.collection)) {
      policy.value = null
      return
    }
    try {
      const loaded = await useModuleRepository(current).statusPolicy()
      policyCache.set(current.collection, loaded)
      policy.value = loaded
    }
    catch {
      // A collection without a status policy (reports, audit logs, the archive…)
      // offers no status actions; the menu simply stays as it is.
      missingPolicies.add(current.collection)
      policy.value = null
    }
  }

  watch(module, () => { void loadPolicy() }, { immediate: true })

  function transitionsOf(row: Record<string, unknown>): RecordStatusTransition[] {
    return statusTransitionsFor(policy.value, statusValueOf(row))
  }

  function labelOf(transition: RecordStatusTransition): string {
    if (transition.action === 'mark') {
      return t('freight.statusActions.mark', { status: transition.to })
    }
    return t(statusActionMeta(transition.action).labelKey)
  }

  /** The "Change Status" submenu for one record, or null when nothing applies. */
  function menuItem(row: Record<string, unknown>, extras: StatusRunExtras = {}): DropdownMenuItem | null {
    const collection = module.value?.collection
    if (!collection) return null
    const items = transitionsOf(row)
      .filter(transition => transition.kind === 'status' || Boolean(statusCommand(collection, transition.action)))
      .filter(transition => extras.allowTransition?.(transition) !== false)
      .map((transition) => {
        const meta = statusActionMeta(transition.action)
        return {
          label: labelOf(transition),
          icon: meta.icon,
          ...(meta.color === 'neutral' ? {} : { color: meta.color }),
          onSelect: () => { void run(row, transition, extras) },
        } satisfies DropdownMenuItem
      })
    if (!items.length) return null
    return {
      label: t('freight.ui.changeStatus'),
      icon: 'i-lucide-circle-dot',
      children: items,
    }
  }

  async function askForReason(transition: RecordStatusTransition): Promise<string | undefined | null> {
    if (!transition.reason) return undefined
    const entered = await prompt({
      titleKey: 'freight.ui.statusReasonTitle',
      descriptionKey: 'freight.ui.statusReasonDescription',
      labelKey: 'lcs.common.reason',
      placeholderKey: 'freight.ui.statusReasonPlaceholder',
      confirmLabelKey: 'lcs.common.confirm',
      confirmColor: 'warning',
      required: true,
    })
    return entered
  }

  async function run(
    row: Record<string, unknown>,
    transition: RecordStatusTransition,
    extras: StatusRunExtras = {},
  ) {
    const current = module.value
    if (!current) return
    const id = String(row.id || '')
    if (!id) return
    const revisionId = String(row.revisionId || row.id || '')
    const meta = statusActionMeta(transition.action)

    if (transition.confirm) {
      const ok = await confirm({
        kind: 'generic',
        title: t('freight.ui.statusChangeTitle', { status: transition.to }),
        description: extras.confirmDescription?.(transition) || t('freight.ui.statusChangeDescription'),
        confirmLabel: labelOf(transition),
        confirmColor: meta.color === 'error'
          ? 'error'
          : meta.color === 'warning' ? 'warning' : 'primary',
      })
      if (!ok) return
    }

    const reason = await askForReason(transition)
    if (reason === null) return

    busyId.value = id
    try {
      if (transition.kind === 'status') {
        await useModuleRepository(current).changeStatus(id, transition.to, reason)
      }
      else {
        const command = statusCommand(current.collection, transition.action)
        if (!command) return
        await lcs.runCommand(`${current.collection}.${transition.action}`, id, key =>
          command({ id, revisionId, reason, key, repositories: lcs }))
      }
      store.reload()
      await options.onChanged?.()
      toast.add({ title: t('freight.ui.statusChanged', { status: transition.to }), color: 'success' })
    }
    catch (error) {
      // A refused transition (closed period, invalid state, permission) is a
      // business-rule message with no field to own it: it goes where the caller
      // renders page-level errors, never into a toast.
      options.onError?.(lcs.errorMessage(error))
    }
    finally {
      busyId.value = ''
    }
  }

  return { policy, busyId, loadPolicy, transitionsOf, menuItem, labelOf, run }
}
