<script setup lang="ts">
/**
 * Reusable create/edit dialog for small configuration entities (attributes,
 * groups, tabs, …). The page owns the draft state and persistence; this only
 * renders the shell, the fields slot and the footer actions.
 */
withDefaults(defineProps<{
  open: boolean
  title: string
  confirmLabel?: string
  cancelLabel?: string
  saving?: boolean
  confirmDisabled?: boolean
}>(), {
  confirmLabel: 'Save',
  cancelLabel: 'Cancel',
  saving: false,
  confirmDisabled: false,
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
      <slot />
    </template>
    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="cancelLabel"
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
