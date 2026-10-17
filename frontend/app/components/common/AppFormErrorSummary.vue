<script setup lang="ts">
/**
 * Form-level error summary.
 *
 * Lists everything the form could not accept — field errors that belong to a
 * hidden tab as well as backend messages with no field to attach to. Every
 * entry is a button that reveals and focuses the offending input, which is the
 * accessible fallback when the user's viewport cannot show the field at all.
 */
import type { ValidationSummaryItem } from '~/composables/common/useFormValidation'

withDefaults(defineProps<{
  items?: ValidationSummaryItem[]
  formErrors?: string[]
  /** Changes the wording of the "correct the fields" heading. */
  title?: string
}>(), {
  items: () => [],
  formErrors: () => [],
  title: '',
})

const emit = defineEmits<{
  select: [key: string]
}>()

const { t } = useI18n()
</script>

<template>
  <div
    v-if="items.length || formErrors.length"
    class="space-y-2"
    role="alert"
    aria-live="assertive"
    data-slot="form-error-summary"
  >
    <UAlert
      color="error"
      variant="subtle"
      icon="i-lucide-alert-circle"
      :title="title || t('validation.summaryTitle')"
      :description="t('validation.summaryCount', { count: items.length + formErrors.length })"
    />

    <ul v-if="items.length" class="space-y-1 ps-1 text-sm">
      <li v-for="item in items" :key="item.key">
        <button
          type="button"
          class="flex w-full items-start gap-2 rounded-md px-2 py-1 text-start text-error underline-offset-2 hover:bg-elevated hover:underline focus-visible:outline-2 focus-visible:outline-primary"
          @click="emit('select', item.key)"
        >
          <UIcon name="i-lucide-arrow-right" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span class="min-w-0 flex-1">
            <span v-if="item.groupLabel" class="font-medium">{{ item.groupLabel }} &rsaquo; </span>{{ item.message }}
          </span>
        </button>
      </li>
    </ul>

    <ul v-if="formErrors.length" class="space-y-1 ps-1 text-sm text-error">
      <li v-for="(message, index) in formErrors" :key="index" class="flex items-start gap-2">
        <UIcon name="i-lucide-alert-circle" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <span class="min-w-0 flex-1">{{ message }}</span>
      </li>
    </ul>
  </div>
</template>