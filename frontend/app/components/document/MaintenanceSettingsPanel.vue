<script setup lang="ts">
const model = defineModel<{ enabled: boolean, reason: string }>({ required: true })
defineProps<{ disabled?: boolean, fieldErrors?: Record<string, string>, formErrors?: string[] }>()
const emit = defineEmits<{ edit: [key: string] }>()
const { t } = useI18n()
</script>

<template>
  <section class="mx-auto w-full max-w-5xl space-y-4 px-6 py-6">
    <CommonAppFormErrorSummary :form-errors="formErrors || []" />
    <UFormField :label="t('maintenance.enabled')" data-field-key="enabled" :error="fieldErrors?.enabled">
      <USwitch
v-model="model.enabled"
:disabled="disabled"
:aria-label="t('maintenance.enabled')"
@update:model-value="emit('edit', 'enabled')" />
    </UFormField>
    <UFormField
:label="t('maintenance.reason')"
data-field-key="reason"
:error="fieldErrors?.reason"
required>
      <UTextarea
v-model="model.reason"
:disabled="disabled"
:maxlength="500"
class="w-full"
@update:model-value="emit('edit', 'reason')" />
    </UFormField>
  </section>
</template>
