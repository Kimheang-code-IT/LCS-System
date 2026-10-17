<script setup lang="ts">
/**
 * Free-text note editor for one table row.
 *
 * A note is prose, not a value: a one-line cell input is too narrow to read or
 * write one, and a wide column would push the real data off screen. So the table
 * shows an icon that indicates whether a note exists, and the text lives in this
 * dialog.
 *
 * The component is deliberately dumb — it owns the draft text and reports a save;
 * the table decides where the value is stored.
 */
const props = withDefaults(defineProps<{
  open: boolean
  title?: string
  modelValue?: string
  disabled?: boolean
  placeholder?: string
}>(), {
  title: '',
  modelValue: '',
  disabled: false,
  placeholder: '',
})

const emit = defineEmits<{
  'update:open': [value: boolean]
  'save': [value: string]
}>()

const { t } = useI18n()

const draft = ref('')

/** Reload the draft from the stored value every time the dialog is opened. */
watch(() => props.open, (open) => {
  if (open) draft.value = String(props.modelValue || '')
}, { immediate: true })

function save() {
  emit('save', draft.value.trim())
  emit('update:open', false)
}
</script>

<template>
  <UModal
    :open="props.open"
    :title="props.title || t('freight.ui.cols.note')"
    :description="t('freight.ui.noteDialogHint')"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <UTextarea
        v-model="draft"
        :rows="5"
        :disabled="props.disabled"
        :placeholder="props.placeholder || t('freight.ui.notePlaceholder')"
        class="w-full"
        autoresize
      />
    </template>
    <template #footer>
      <div class="flex w-full items-center justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('actions.cancel')"
          @click="emit('update:open', false)"
        />
        <UButton
          color="primary"
          :label="t('actions.save')"
          :disabled="props.disabled"
          @click="save"
        />
      </div>
    </template>
  </UModal>
</template>
