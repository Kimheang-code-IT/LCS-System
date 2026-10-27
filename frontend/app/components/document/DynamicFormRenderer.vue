<script setup lang="ts">
import type { ComponentTabAttribute, ComponentTabGroup } from '~/types/component-config'
import {
  componentFormGridClass,
  componentInputType,
  resolveComponentLayout,
  visibleComponentAttributes,
} from '~/utils/freight/component-layout'
import { formFieldError } from '~/utils/validation/form-field-error'

const props = withDefaults(defineProps<{
  group: ComponentTabGroup
  modelValue: Record<string, unknown>
  references?: Record<string, Record<string, string>>
  editable?: boolean
  saving?: boolean
  /** Errors keyed by attribute code, or by canonical `<prefix>.<code>` path. */
  errors?: Record<string, string>
  /** Canonical path used for `data-field-key` and error lookup. */
  fieldKeyPrefix?: string
  showSubmit?: boolean
  submitLabelKey?: string
}>(), {
  references: () => ({}),
  editable: true,
  saving: false,
  errors: () => ({}),
  fieldKeyPrefix: '',
  showSubmit: true,
  submitLabelKey: 'freight.ui.saveChanges',
})

const emit = defineEmits<{
  'update:field': [code: string, value: unknown]
  'submit': []
}>()

const { t, te, locale } = useI18n()

const layout = computed(() => resolveComponentLayout(props.group))
const attributes = computed(() => visibleComponentAttributes(props.group))
const gridClass = computed(() => componentFormGridClass(layout.value.formColumns))
const prefix = computed(() => props.fieldKeyPrefix || `${props.group.id}.0`)

function fieldKey(code: string) {
  return `${prefix.value}.${code}`
}

function errorFor(code: string) {
  // Never `''`: `UFormField.error` casts an empty string to `true`.
  return formFieldError(props.errors, code) || formFieldError(props.errors, fieldKey(code))
}

function attributeLabel(attribute: ComponentTabAttribute) {
  if (te(`freight.fields.${attribute.code}`)) return t(`freight.fields.${attribute.code}`)
  return String(locale.value === 'km' && attribute.labelKm ? attribute.labelKm : attribute.label)
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

function valueOf(attribute: ComponentTabAttribute) {
  return props.modelValue[attribute.code]
}

function setValue(attribute: ComponentTabAttribute, value: unknown) {
  emit('update:field', attribute.code, value)
}
</script>

<template>
  <div class="space-y-4">
    <div :class="gridClass">
      <UFormField
        v-for="attribute in attributes"
        :key="attribute.code"
        :label="attributeLabel(attribute)"
        :required="attribute.isRequired"
        :error="errorFor(attribute.code)"
        :data-field-key="fieldKey(attribute.code)"
      >
        <UCheckbox
          v-if="attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean'"
          :model-value="Boolean(valueOf(attribute))"
          :disabled="!editable"
          @update:model-value="setValue(attribute, $event)"
        />
        <UInputNumber
          v-else-if="['number', 'integer', 'decimal', 'money'].includes(attribute.fieldType)"
          :model-value="Number(valueOf(attribute) ?? 0)"
          :disabled="!editable"
          :step-snapping="false"
          class="w-full"
          @update:model-value="setValue(attribute, $event)"
        />
        <UTextarea
          v-else-if="attribute.fieldType === 'textarea'"
          :model-value="String(valueOf(attribute) ?? '')"
          :disabled="!editable"
          :rows="3"
          class="w-full"
          @update:model-value="setValue(attribute, $event)"
        />
        <USelect
          v-else-if="['select', 'currency', 'multi_select', 'reference'].includes(attribute.fieldType)"
          :model-value="(valueOf(attribute) as string | string[] | undefined)"
          :items="optionItems(attribute)"
          :multiple="attribute.fieldType === 'multi_select'"
          :disabled="!editable"
          class="w-full"
          @update:model-value="setValue(attribute, $event)"
        />
        <UInput
          v-else
          :model-value="String(valueOf(attribute) ?? '')"
          :type="componentInputType(attribute)"
          :placeholder="attribute.placeholder || undefined"
          :disabled="!editable"
          class="w-full"
          @update:model-value="setValue(attribute, $event)"
        />
      </UFormField>
    </div>

    <div v-if="showSubmit && editable" class="flex justify-end">
      <UButton
        icon="i-lucide-save"
        :label="t(submitLabelKey)"
        :loading="saving"
        @click="emit('submit')"
      />
    </div>
  </div>
</template>
