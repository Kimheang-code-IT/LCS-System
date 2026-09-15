<script setup lang="ts">
const open = defineModel<boolean>('open', { default: false })

const props = withDefaults(defineProps<{
  title?: string
  titleKey?: string
  description?: string
  descriptionKey?: string
  confirmLabel?: string
  confirmLabelKey?: string
  cancelLabel?: string
  cancelLabelKey?: string
  confirmColor?: 'error' | 'primary' | 'neutral' | 'warning'
  loading?: boolean
  ui?: Record<string, unknown>
}>(), {
  confirmColor: 'error',
  loading: false,
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const { t, te } = useI18n()

const resolvedTitle = computed(() => {
  if (props.title) return props.title
  if (props.titleKey && te(props.titleKey)) return t(props.titleKey)
  return t('docetra.common.confirmTitle')
})

const resolvedDescription = computed(() => {
  if (props.description) return props.description
  if (props.descriptionKey && te(props.descriptionKey)) return t(props.descriptionKey)
  return ''
})

const resolvedConfirm = computed(() => {
  if (props.confirmLabel) return props.confirmLabel
  if (props.confirmLabelKey && te(props.confirmLabelKey)) return t(props.confirmLabelKey)
  return t('docetra.common.confirm')
})

const resolvedCancel = computed(() => {
  if (props.cancelLabel) return props.cancelLabel
  if (props.cancelLabelKey && te(props.cancelLabelKey)) return t(props.cancelLabelKey)
  return t('docetra.common.cancel')
})

function onCancel() {
  open.value = false
  emit('cancel')
}

function onConfirm() {
  emit('confirm')
}
</script>

<template>
  <UModal v-model:open="open" :dismissible="false" :ui="props.ui">
    <template #content>
      <UCard>
        <template #header>
          <h3 class="text-base font-semibold text-highlighted">
            {{ resolvedTitle }}
          </h3>
        </template>

        <p v-if="resolvedDescription" class="text-sm text-muted">
          {{ resolvedDescription }}
        </p>
        <slot />

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="loading"
              @click="onCancel"
            >
              {{ resolvedCancel }}
            </UButton>
            <UButton
              :color="confirmColor"
              :loading="loading"
              @click="onConfirm"
            >
              {{ resolvedConfirm }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
