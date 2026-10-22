<script setup lang="ts">
/**
 * Form-level messages that belong to no single input.
 *
 * Field errors are **not** repeated here: every one of them is already
 * rendered under its own control by `UFormField`, and the submit handler moves
 * focus to the first invalid field (opening its tab first), so a duplicated
 * list at the top of the page adds nothing but noise.
 *
 * What remains is the failure the form genuinely cannot attach to an input — a
 * backend key this form does not render, a business-rule refusal such as a
 * closed accounting period, or a transport failure. Without this line those
 * would be reported nowhere at all, so it is kept as a slim, persistent line
 * rather than a toast.
 */

withDefaults(defineProps<{
  formErrors?: string[]
  /** Optional heading, for a caller whose messages need their own context. */
  title?: string
}>(), {
  formErrors: () => [],
  title: '',
})
</script>

<template>
  <div
    v-if="formErrors.length"
    class="space-y-1 text-sm text-error"
    role="alert"
    aria-live="assertive"
    data-slot="form-error-summary"
  >
    <p v-if="title" class="font-medium">{{ title }}</p>
    <p
      v-for="(message, index) in formErrors"
      :key="index"
      class="flex items-start gap-2"
    >
      <UIcon name="i-lucide-alert-circle" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span class="min-w-0 flex-1">{{ message }}</span>
    </p>
  </div>
</template>