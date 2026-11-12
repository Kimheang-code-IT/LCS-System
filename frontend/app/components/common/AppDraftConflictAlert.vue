<script setup lang="ts">
/**
 * Restore/Discard choice for a local draft written against an older server
 * copy. One component so every document form explains the conflict the same
 * way; the owning form decides what Restore applies.
 */
withDefaults(defineProps<{
  savedAt?: string
}>(), {
  savedAt: '',
})

const emit = defineEmits<{
  restore: []
  discard: []
}>()

const { t } = useI18n()
</script>

<template>
  <UAlert
    color="warning"
    variant="subtle"
    icon="i-lucide-triangle-alert"
    :title="t('freight.ui.draftConflictTitle')"
    :description="t('freight.ui.draftConflictDescription', { time: savedAt })">
    <template #actions>
      <UButton
        size="sm"
        color="warning"
        variant="soft"
        :label="t('freight.ui.restoreDraft')"
        @click="emit('restore')" />
      <UButton
        size="sm"
        color="neutral"
        variant="ghost"
        :label="t('freight.ui.discardDraft')"
        @click="emit('discard')" />
    </template>
  </UAlert>
</template>
