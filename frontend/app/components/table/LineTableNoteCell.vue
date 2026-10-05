<script setup lang="ts">
const props = defineProps<{
  modelValue?: unknown
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [string]
}>()

const { t } = useI18n()
const open = ref(false)
const draft = ref('')

const note = computed(() => String(props.modelValue ?? ''))
const hasNote = computed(() => note.value.trim().length > 0)

watch(open, (value) => {
  if (value) draft.value = note.value
})

function openDialog() {
  if (props.disabled) return
  draft.value = note.value
  open.value = true
}

function save() {
  emit('update:modelValue', draft.value.trim())
  open.value = false
}
</script>

<template>
  <div>
    <UButton
      color="neutral"
      variant="ghost"
      size="xs"
      square
      :icon="hasNote ? 'i-lucide-sticky-note' : 'i-lucide-notebook-pen'"
      :class="hasNote ? 'text-primary' : 'text-muted'"
      :disabled="disabled"
      :aria-label="t('freight.ui.rowNote')"
      :title="hasNote ? note : t('freight.ui.addRowNote')"
      @click="openDialog"
    />

    <UModal
      v-model:open="open"
      :title="t('freight.ui.rowNoteTitle')"
      :ui="{ content: 'w-[calc(100%-2rem)] max-w-lg sm:max-w-lg' }"
    >
      <template #body>
        <UTextarea
          v-model="draft"
          :rows="5"
          :placeholder="t('freight.ui.rowNotePlaceholder')"
          :aria-label="t('freight.ui.rowNoteTitle')"
          class="w-full"
        />
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            :label="t('actions.cancel')"
            @click="open = false"
          />
          <UButton
            color="primary"
            size="sm"
            :label="t('actions.save')"
            @click="save"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>