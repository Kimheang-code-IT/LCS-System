<script setup lang="ts">
/**
 * Reusable create/edit dialog for small configuration entities (attributes,
 * groups, tabs, …). The page owns the draft state and persistence; this only
 * renders the shell, the fields slot and the footer actions.
 *
 * Validation copy is never a toast here: field errors are rendered by the
 * slotted `UFormField`s, and anything the form could not attach to a field is
 * shown above them through `formErrors`.
 */
withDefaults(defineProps<{
  open: boolean
  title: string
  confirmLabel?: string
  cancelLabel?: string
  saving?: boolean
  confirmDisabled?: boolean
  formErrors?: string[]
}>(), {
  confirmLabel: 'Save',
  cancelLabel: 'Cancel',
  saving: false,
  confirmDisabled: false,
  formErrors: () => [],
})

const emit = defineEmits<{
  'update:open': [boolean]
  'confirm': []
}>()
</script>

<template>
  <UModal
    :open="open"
    :title="title"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <CommonAppFormErrorSummary
        v-if="formErrors.length"
        class="mb-4"
        :form-errors="formErrors"
      />
      <slot />
    </template>
    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="cancelLabel"
          :disabled="saving"
          @click="emit('update:open', false)"
        />
        <UButton
          color="primary"
          :label="confirmLabel"
          :loading="saving"
          :disabled="confirmDisabled"
          @click="emit('confirm')"
        />
      </div>
    </template>
  </UModal>
</template>