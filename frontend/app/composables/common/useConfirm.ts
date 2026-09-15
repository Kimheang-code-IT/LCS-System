import { reactive } from 'vue'

export type ConfirmKind = 'delete' | 'save' | 'submit' | 'update' | 'unsaved' | 'generic'

export type ConfirmColor = 'error' | 'primary' | 'neutral' | 'warning'

export interface ConfirmOptions {
  kind?: ConfirmKind
  title?: string
  titleKey?: string
  description?: string
  descriptionKey?: string
  /** Params for i18n description (e.g. { n: 3 }). */
  descriptionParams?: Record<string, unknown>
  confirmLabel?: string
  confirmLabelKey?: string
  cancelLabel?: string
  cancelLabelKey?: string
  confirmColor?: ConfirmColor
  /** Used by delete preset: number of items. */
  count?: number
}

type ConfirmState = {
  open: boolean
  title?: string
  titleKey?: string
  description?: string
  descriptionKey?: string
  descriptionParams?: Record<string, unknown>
  confirmLabel?: string
  confirmLabelKey?: string
  cancelLabel?: string
  cancelLabelKey?: string
  confirmColor: ConfirmColor
  loading: boolean
}

const PRESETS: Record<ConfirmKind, Partial<ConfirmOptions> & { confirmColor: ConfirmColor }> = {
  delete: {
    titleKey: 'docetra.confirm.deleteTitle',
    descriptionKey: 'docetra.actions.deleteConfirm',
    confirmLabelKey: 'docetra.rowActions.delete',
    confirmColor: 'error',
  },
  save: {
    titleKey: 'docetra.confirm.saveTitle',
    descriptionKey: 'docetra.confirm.saveDescription',
    confirmLabelKey: 'docetra.common.save',
    confirmColor: 'primary',
  },
  submit: {
    titleKey: 'docetra.confirm.submitTitle',
    descriptionKey: 'docetra.confirm.submitDescription',
    confirmLabelKey: 'docetra.confirm.submit',
    confirmColor: 'primary',
  },
  update: {
    titleKey: 'docetra.confirm.updateTitle',
    descriptionKey: 'docetra.confirm.updateDescription',
    confirmLabelKey: 'docetra.confirm.update',
    confirmColor: 'primary',
  },
  unsaved: {
    titleKey: 'docetra.common.unsavedTitle',
    descriptionKey: 'docetra.common.unsavedDescription',
    confirmLabelKey: 'docetra.common.discardChanges',
    cancelLabelKey: 'docetra.common.keepEditing',
    confirmColor: 'warning',
  },
  generic: {
    titleKey: 'docetra.common.confirmTitle',
    descriptionKey: 'docetra.confirm.genericDescription',
    confirmLabelKey: 'docetra.common.confirm',
    confirmColor: 'primary',
  },
}

/** UI state only — resolvers kept outside to avoid SSR / reactivity issues. */
const confirmState = reactive<ConfirmState>({
  open: false,
  confirmColor: 'primary',
  loading: false,
})

let pendingResolve: ((value: boolean) => void) | null = null

function close(result: boolean) {
  confirmState.open = false
  confirmState.loading = false
  const resolve = pendingResolve
  pendingResolve = null
  resolve?.(result)
}

/**
 * Global reusable confirm dialog.
 * Usage: `const ok = await confirm({ kind: 'delete', count: 2 })`
 */
export function useConfirm() {
  function confirm(options: ConfirmOptions = {}): Promise<boolean> {
    if (!import.meta.client) return Promise.resolve(false)

    const kind = options.kind || 'generic'
    const preset = PRESETS[kind]
    const count = options.count ?? 1

    // If a dialog is already open, reject the previous waiter.
    if (pendingResolve) {
      pendingResolve(false)
      pendingResolve = null
    }

    confirmState.title = options.title
    confirmState.titleKey = options.titleKey || preset.titleKey
    confirmState.description = options.description
    confirmState.descriptionKey = options.descriptionKey || preset.descriptionKey
    confirmState.descriptionParams = options.descriptionParams || (kind === 'delete' ? { n: count } : undefined)
    confirmState.confirmLabel = options.confirmLabel
    confirmState.confirmLabelKey = options.confirmLabelKey || preset.confirmLabelKey
    confirmState.cancelLabel = options.cancelLabel
    confirmState.cancelLabelKey = options.cancelLabelKey || preset.cancelLabelKey
    confirmState.confirmColor = options.confirmColor || preset.confirmColor
    confirmState.loading = false
    confirmState.open = true

    return new Promise<boolean>((resolve) => {
      pendingResolve = resolve
    })
  }

  function setLoading(loading: boolean) {
    confirmState.loading = loading
  }

  function accept() {
    close(true)
  }

  function dismiss() {
    close(false)
  }

  return {
    confirmState,
    confirm,
    setLoading,
    accept,
    dismiss,
  }
}
