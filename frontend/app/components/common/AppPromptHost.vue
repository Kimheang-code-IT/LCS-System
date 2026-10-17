<script setup lang="ts">
/**
 * Single app-wide prompt dialog host (one value + confirm).
 * Driven by usePrompt() — mount once in app.vue.
 */
import { usePrompt } from '~/composables/common/usePrompt'

const { promptState, accept, dismiss } = usePrompt()
const { t, te } = useI18n()

const open = computed({
  get: () => promptState.open,
  set: (value: boolean) => {
    if (!value && promptState.open) dismiss()
  },
})

const title = computed(() => {
  if (promptState.title) return promptState.title
  if (promptState.titleKey && te(promptState.titleKey)) return t(promptState.titleKey)
  return t('lcs.common.confirmTitle')
})

const description = computed(() => {
  if (promptState.description) return promptState.description
  if (promptState.descriptionKey && te(promptState.descriptionKey)) return t(promptState.descriptionKey)
  return ''
})

const label = computed(() => {
  if (promptState.label) return promptState.label
  if (promptState.labelKey && te(promptState.labelKey)) return t(promptState.labelKey)
  return t('lcs.common.reason')
})

const placeholder = computed(() =>
  promptState.placeholderKey && te(promptState.placeholderKey) ? t(promptState.placeholderKey) : '',
)

const confirmLabel = computed(() => {
  if (promptState.confirmLabel) return promptState.confirmLabel
  if (promptState.confirmLabelKey && te(promptState.confirmLabelKey)) return t(promptState.confirmLabelKey)
  return t('lcs.common.confirm')
})

const confirmDisabled = computed(() => promptState.required && !promptState.value.trim())
</script>

<template>
  <CommonAppConfirmDialog
    v-model:open="open"
    :title="title"
    :description="description"
    :confirm-label="confirmLabel"
    :confirm-color="promptState.confirmColor"
    :loading="promptState.loading"
    :confirm-disabled="confirmDisabled"
    :ui="{ overlay: 'z-[200]', content: 'z-[200]' }"
    @confirm="accept"
    @cancel="dismiss"
  >
    <div class="mt-3 space-y-1">
      <label class="text-sm font-medium text-highlighted">{{ label }}</label>
      <UTextarea
        v-model="promptState.value"
        :rows="3"
        autoresize
        :placeholder="placeholder || undefined"
      />
    </div>
  </CommonAppConfirmDialog>
</template>
