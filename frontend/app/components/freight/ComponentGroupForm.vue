<script setup lang="ts">
import type { ComponentTabAttribute, ComponentTabGroup } from '~/types/component-config'

const props = defineProps<{
  group: ComponentTabGroup
  references: Record<string, Record<string, string>>
  modelValue: Array<Record<string, unknown>>
  editable?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [Array<Record<string, unknown>>]
  'save': []
}>()

const { t } = useI18n()

const row = computed<Record<string, unknown>>(() => props.modelValue[0] || {})

function setValue(code: string, value: unknown) {
  emit('update:modelValue', [{ ...row.value, [code]: value }])
}

function optionItems(attribute: ComponentTabAttribute) {
  if (attribute.fieldType === 'reference' && attribute.referenceType) {
    return Object.entries(props.references[attribute.referenceType] || {})
      .map(([value, label]) => ({ label: String(label), value: String(value) }))
  }
  const options = Array.isArray(attribute.options) ? attribute.options : []
  return options.map(option => (typeof option === 'string'
    ? { label: option, value: option }
    : { label: String(option.label), value: String(option.value) }))
}
</script>

<template>
  <div class="space-y-4">
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <UFormField
        v-for="attribute in group.attributes"
        :key="attribute.code"
        :label="attribute.label"
        :required="attribute.isRequired"
      >
        <UCheckbox
          v-if="attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean'"
          :model-value="Boolean(row[attribute.code])"
          :disabled="!editable"
          @update:model-value="setValue(attribute.code, $event)" />
        <UInputNumber
          v-else-if="['number', 'decimal', 'money'].includes(attribute.fieldType)"
          :model-value="Number(row[attribute.code] ?? 0)"
          :disabled="!editable"
          class="w-full"
          @update:model-value="setValue(attribute.code, $event)" />
        <UTextarea
          v-else-if="attribute.fieldType === 'textarea'"
          :model-value="String(row[attribute.code] ?? '')"
          :disabled="!editable"
          class="w-full"
          @update:model-value="setValue(attribute.code, $event)" />
        <USelect
          v-else-if="['select', 'currency', 'multi_select', 'reference'].includes(attribute.fieldType)"
          :model-value="(row[attribute.code] as string | string[] | undefined)"
          :items="optionItems(attribute)"
          :multiple="attribute.fieldType === 'multi_select'"
          :disabled="!editable"
          class="w-full"
          @update:model-value="setValue(attribute.code, $event)" />
        <UInput
          v-else
          :model-value="String(row[attribute.code] ?? '')"
          :type="attribute.fieldType === 'date' ? 'date' : attribute.fieldType === 'datetime' ? 'datetime-local' : 'text'"
          :placeholder="attribute.placeholder || undefined"
          :disabled="!editable"
          class="w-full"
          @update:model-value="setValue(attribute.code, $event)" />
      </UFormField>
    </div>

    <div v-if="editable" class="flex justify-end">
      <UButton
        icon="i-lucide-save"
        :label="t('freight.ui.saveChanges')"
        :loading="saving"
        @click="emit('save')" />
    </div>
  </div>
</template>
