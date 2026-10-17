import { reactive } from 'vue'

export interface PromptOptions {
  title?: string
  titleKey?: string
  description?: string
  descriptionKey?: string
  label?: string
  labelKey?: string
  placeholderKey?: string
  confirmLabel?: string
  confirmLabelKey?: string
  confirmColor?: 'error' | 'primary' | 'neutral' | 'warning'
  /** The confirm button stays disabled until something is typed. */
  required?: boolean
  value?: string
}

interface PromptState {
  open: boolean
  title: string
  titleKey: string
  description: string
  descriptionKey: string
  label: string
  labelKey: string
  placeholderKey: string
  confirmLabel: string
  confirmLabelKey: string
  confirmColor: 'error' | 'primary' | 'neutral' | 'warning'
  required: boolean
  value: string
  loading: boolean
}

/** UI state only — the resolver stays outside to avoid reactivity issues. */
const promptState = reactive<PromptState>({
  open: false,
  title: '',
  titleKey: '',
  description: '',
  descriptionKey: '',
  label: '',
  labelKey: '',
  placeholderKey: '',
  confirmLabel: '',
  confirmLabelKey: '',
  confirmColor: 'primary',
  required: true,
  value: '',
  loading: false,
})

let pendingResolve: ((value: string | null) => void) | null = null

function close(result: string | null) {
  promptState.open = false
  promptState.loading = false
  const resolve = pendingResolve
  pendingResolve = null
  resolve?.(result)
}

/**
 * Global reusable text-prompt dialog — the confirmation twin that collects one
 * value, used for the reversal reason. Mount `AppPromptHost` once in `app.vue`.
 */
export function usePrompt() {
  function prompt(options: PromptOptions = {}): Promise<string | null> {
    if (!import.meta.client) return Promise.resolve(null)
    if (pendingResolve) {
      pendingResolve(null)
      pendingResolve = null
    }
    promptState.title = options.title || ''
    promptState.titleKey = options.titleKey || ''
    promptState.description = options.description || ''
    promptState.descriptionKey = options.descriptionKey || ''
    promptState.label = options.label || ''
    promptState.labelKey = options.labelKey || ''
    promptState.placeholderKey = options.placeholderKey || ''
    promptState.confirmLabel = options.confirmLabel || ''
    promptState.confirmLabelKey = options.confirmLabelKey || ''
    promptState.confirmColor = options.confirmColor || 'primary'
    promptState.required = options.required !== false
    promptState.value = options.value || ''
    promptState.loading = false
    promptState.open = true
    return new Promise<string | null>((resolve) => {
      pendingResolve = resolve
    })
  }

  function setLoading(loading: boolean) {
    promptState.loading = loading
  }

  function accept() {
    if (promptState.required && !promptState.value.trim()) return
    close(promptState.value.trim())
  }

  function dismiss() {
    close(null)
  }

  return { promptState, prompt, setLoading, accept, dismiss }
}
