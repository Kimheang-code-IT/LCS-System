<script setup lang="ts">
import type { FreightField } from '~/config/freight-modules'
import { useFreightLabel } from '~/composables/freight/useFreight'
import { documentSequenceTypeLabel, isDocumentSequenceType } from '~/utils/document-sequences'
import { resolveFormFieldHelp } from '~/utils/field-help'
import { referenceOptionSource, referenceSelectItems } from '~/utils/freight/reference-options'

defineProps<{
  fields: FreightField[]
  model: Record<string, unknown>
  disabled?: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  update: [key: string, value: unknown]
}>()

const { t, te } = useI18n()
const { fieldLabel } = useFreightLabel()

const store = useFreightStore()

function selectOptionLabel(field: FreightField, value: string, explicitLabel?: string) {
  if (explicitLabel) return explicitLabel
  if (field.key === 'documentType' && isDocumentSequenceType(value)) {
    return documentSequenceTypeLabel(value)
  }
  return value
}

// Master Data pages are the single source of truth for these selects; static
// `field.options` are ignored when a reference source exists.
function itemsFor(field: FreightField) {
  const source = referenceOptionSource(field.key)
  if (source) return referenceSelectItems(store.list(source.collection), source)
  return (field.options || []).flatMap((option) => {
    if (option && typeof option === 'object') {
      const value = String(option.value ?? '').trim()
      if (!value) return []
      const explicit = String(option.label || '').trim()
      return [{ label: selectOptionLabel(field, value, explicit || undefined), value }]
    }
    const value = String(option).trim()
    if (!value) return []
    return [{ label: selectOptionLabel(field, value), value }]
  })
}

function helpFor(field: FreightField) {
  return resolveFormFieldHelp({
    key: field.key,
    label: fieldLabel(field),
    help: field.help,
    helpKey: field.helpKey,
    computed: field.computed,
  }, t, te)
}

function checkboxTrue(field: FreightField) {
  return String(field.options?.[0] ?? 'Yes')
}

function checkboxFalse(field: FreightField) {
  return String(field.options?.[1] ?? 'No')
}

function spanClass(field: FreightField) {
  return field.colSpan === 2 || field.type === 'textarea' ? 'sm:col-span-2' : ''
}
</script>

<template>
  <div
    class="grid min-w-0 grid-cols-1 sm:grid-cols-2"
    :class="compact ? 'gap-x-4 gap-y-3' : 'gap-x-5 gap-y-5'"
  >
    <template v-for="field in fields" :key="field.key">
      <UFormField
        v-if="field.type === 'checkbox'"
        :help="helpFor(field)"
        class="min-w-0"
        :class="spanClass(field)"
      >
        <div class="flex min-h-11 items-center pt-1">
          <UCheckbox
            :model-value="model[field.key]"
            :true-value="checkboxTrue(field)"
            :false-value="checkboxFalse(field)"
            :disabled="disabled || field.computed"
            size="md"
            @update:model-value="emit('update', field.key, $event)"
          >
            <template #label>
              <span class="inline-flex items-center gap-2 text-base text-highlighted">
                <span>{{ fieldLabel(field) }}</span>
                <UTooltip :text="helpFor(field)">
                  <UIcon name="i-lucide-info" class="size-4 text-muted" />
                </UTooltip>
              </span>
            </template>
          </UCheckbox>
        </div>
      </UFormField>

      <UFormField
        v-else
        :label="fieldLabel(field)"
        :required="Boolean(field.required)"
        :help="helpFor(field)"
        class="min-w-0"
        :class="spanClass(field)"
      >
        <CommonAppReferenceSelect
          v-if="field.type === 'select'"
          :model-value="model[field.key]"
          :items="itemsFor(field)"
          :reference-key="field.key"
          :placeholder="fieldLabel(field)"
          :disabled="disabled || field.computed"
          size="md"
          class="w-full"
          @update:model-value="emit('update', field.key, $event)"
        />
        <CommonAppReferenceSelect
          v-else-if="field.type === 'multiselect'"
          multiple
          :model-value="Array.isArray(model[field.key]) ? (model[field.key] as unknown[]).map(String) : []"
          :items="itemsFor(field)"
          :reference-key="field.key"
          :placeholder="fieldLabel(field)"
          :disabled="disabled"
          size="md"
          class="w-full"
          @update:model-value="emit('update', field.key, $event)"
        />
        <UInputNumber
          v-else-if="field.type === 'number'"
          :model-value="Number(model[field.key] || 0)"
          :disabled="disabled || field.computed"
          :increment="false"
          :decrement="false"
          size="md"
          class="w-full"
          @update:model-value="emit('update', field.key, $event ?? 0)"
        />
        <UTextarea
          v-else-if="field.type === 'textarea'"
          :model-value="String(model[field.key] ?? '')"
          :disabled="disabled"
          :rows="compact ? 2 : 4"
          size="md"
          autoresize
          class="w-full"
          @update:model-value="emit('update', field.key, $event)"
        />
        <CommonAppInputDate
          v-else-if="field.type === 'date' || field.type === 'datetime'"
          :model-value="String(model[field.key] ?? '')"
          :granularity="field.type === 'datetime' ? 'minute' : 'day'"
          :disabled="disabled || field.computed"
          :required="Boolean(field.required)"
          size="md"
          class="w-full"
          @update:model-value="emit('update', field.key, $event)"
        />
        <UInput
          v-else-if="field.type === 'password'"
          type="password"
          :model-value="String(model[field.key] ?? '')"
          :disabled="disabled"
          size="md"
          class="w-full"
          @update:model-value="emit('update', field.key, $event)"
        />
        <UInput
          v-else-if="field.type === 'file'"
          type="file"
          :disabled="disabled"
          size="md"
          class="w-full"
          @change="(event: Event) => {
            const file = (event.target as HTMLInputElement).files?.[0]
            emit('update', field.key, file?.name || model[field.key])
          }"
        />
        <UInput
          v-else
          :model-value="String(model[field.key] ?? '')"
          :disabled="disabled || field.computed"
          size="md"
          class="w-full"
          @update:model-value="emit('update', field.key, $event)"
        />
      </UFormField>
    </template>
  </div>
</template>
