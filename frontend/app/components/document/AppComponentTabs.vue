<script setup lang="ts">
import type { ComponentTabAttribute, ComponentTabGroup, ComponentTabRuntime } from '~/types/freight/component-config'
import { componentGroupToFreightTable } from '~/utils/freight/component-tabs'

const props = defineProps<{
  tab: ComponentTabRuntime
  references: Record<string, Record<string, string>>
  rowsByGroup: Record<string, Array<Record<string, unknown>>>
  editable?: boolean
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:rows': [groupId: string, rows: Array<Record<string, unknown>>]
  'save-group': [groupId: string]
}>()

const { t } = useI18n()

function rowOf(groupId: string): Record<string, unknown> {
  return (props.rowsByGroup[groupId] || [])[0] || {}
}

function setValue(group: ComponentTabGroup, code: string, value: unknown) {
  const rows = props.rowsByGroup[group.id] || []
  emit('update:rows', group.id, [{ ...(rows[0] || {}), [code]: value }])
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
  <div class="space-y-8">
    <section v-for="group in tab.groups" :key="group.id" class="space-y-3">
      <h3 class="text-sm font-semibold text-highlighted">{{ group.name }}</h3>

      <FreightDynamicDataTable
        v-if="group.renderMode === 'table'"
        :table="componentGroupToFreightTable(group, references)"
        :model-value="rowsByGroup[group.id] || []"
        :disabled="!editable"
        :saving="saving"
        @update:model-value="emit('update:rows', group.id, $event)"
        @save="emit('save-group', group.id)"
      />

      <div v-else class="space-y-4">
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <UFormField
            v-for="attribute in group.attributes"
            :key="attribute.code"
            :label="attribute.label"
            :required="attribute.isRequired"
          >
            <UCheckbox
              v-if="attribute.fieldType === 'checkbox' || attribute.fieldType === 'boolean'"
              :model-value="Boolean(rowOf(group.id)[attribute.code])"
              :disabled="!editable"
              @update:model-value="setValue(group, attribute.code, $event)"
            />
            <UInputNumber
              v-else-if="['number', 'decimal', 'money'].includes(attribute.fieldType)"
              :model-value="Number(rowOf(group.id)[attribute.code] ?? 0)"
              :disabled="!editable"
              class="w-full"
              @update:model-value="setValue(group, attribute.code, $event)"
            />
            <UTextarea
              v-else-if="attribute.fieldType === 'textarea'"
              :model-value="String(rowOf(group.id)[attribute.code] ?? '')"
              :disabled="!editable"
              class="w-full"
              @update:model-value="setValue(group, attribute.code, $event)"
            />
            <USelect
              v-else-if="['select', 'currency', 'multi_select', 'reference'].includes(attribute.fieldType)"
              :model-value="(rowOf(group.id)[attribute.code] as string | string[] | undefined)"
              :items="optionItems(attribute)"
              :multiple="attribute.fieldType === 'multi_select'"
              :disabled="!editable"
              class="w-full"
              @update:model-value="setValue(group, attribute.code, $event)"
            />
            <UInput
              v-else
              :model-value="String(rowOf(group.id)[attribute.code] ?? '')"
              :type="attribute.fieldType === 'date' ? 'date' : attribute.fieldType === 'datetime' ? 'datetime-local' : 'text'"
              :placeholder="attribute.placeholder || undefined"
              :disabled="!editable"
              class="w-full"
              @update:model-value="setValue(group, attribute.code, $event)"
            />
          </UFormField>
        </div>

        <div v-if="editable" class="flex justify-end">
          <UButton
            icon="i-lucide-save"
            :label="t('freight.ui.saveChanges')"
            :loading="saving"
            @click="emit('save-group', group.id)"
          />
        </div>
      </div>
    </section>

    <FreightJobEmptyState
      v-if="!tab.groups.length"
      :title="t('freight.ui.noColumnsConfigured')"
      :description="t('freight.ui.noColumnsConfiguredHint')"
      icon="i-lucide-columns-3"
    />
  </div>
</template>
