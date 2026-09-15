<script setup lang="ts">
import type { DynamicTableColumnDef, DynamicTableColumnType } from '~/types/docetra/configuration'
import { createClientId } from '~/utils/client-id'

const model = defineModel<DynamicTableColumnDef[]>({ default: () => [] })

const { t } = useI18n()

const typeItems = computed(() => ([
  { label: t('docetra.config.tableColumnTypes.text'), value: 'text' },
  { label: t('docetra.config.tableColumnTypes.number'), value: 'number' },
  { label: t('docetra.config.tableColumnTypes.date'), value: 'date' },
  { label: t('docetra.config.tableColumnTypes.select'), value: 'select' },
] satisfies Array<{ label: string, value: DynamicTableColumnType }>))

function addColumn() {
  const order = model.value.length
  model.value = [
    ...model.value,
    {
      id: createClientId('col'),
      key: `column_${order + 1}`,
      label: t('docetra.config.tableColumnDefault', { n: order + 1 }),
      type: 'text',
      required: false,
      order,
    },
  ]
}

function updateColumn(id: string, patch: Partial<DynamicTableColumnDef>) {
  model.value = model.value.map(column => (column.id === id ? { ...column, ...patch } : column))
}

function removeColumn(id: string) {
  model.value = model.value
    .filter(column => column.id !== id)
    .map((column, index) => ({ ...column, order: index }))
}

function onReorder(items: DynamicTableColumnDef[]) {
  model.value = items.map((column, index) => ({ ...column, order: index }))
}

function optionsText(column: DynamicTableColumnDef) {
  return (column.options || []).join(', ')
}

function updateOptions(column: DynamicTableColumnDef, raw: string) {
  const options = raw.split(',').map(item => item.trim()).filter(Boolean)
  updateColumn(String(column.id), { options: options.length ? options : undefined })
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm text-muted">
        {{ t('docetra.config.tableColumnsHelp') }}
      </p>
      <UButton icon="i-lucide-plus" size="sm" @click="addColumn">
        {{ t('docetra.config.addTableColumn') }}
      </UButton>
    </div>

    <CommonAppSortableList :items="model" @reorder="onReorder">
      <template #default="{ item }">
        <div class="grid gap-2 sm:grid-cols-12 sm:items-center">
          <UInput
            :model-value="item.key"
            class="sm:col-span-2"
            size="sm"
            :placeholder="t('docetra.fields.code')"
            @update:model-value="updateColumn(item.id, { key: String($event) })"
          />
          <UInput
            :model-value="item.label"
            class="sm:col-span-3"
            size="sm"
            :placeholder="t('docetra.fields.label')"
            @update:model-value="updateColumn(item.id, { label: String($event) })"
          />
          <USelect
            :model-value="item.type"
            class="sm:col-span-2"
            size="sm"
            :items="typeItems"
            @update:model-value="updateColumn(item.id, { type: $event as DynamicTableColumnType })"
          />
          <UInput
            v-if="item.type === 'select'"
            :model-value="optionsText(item)"
            class="sm:col-span-3"
            size="sm"
            :placeholder="t('docetra.config.tableColumnOptionsPlaceholder')"
            @update:model-value="updateOptions(item, String($event))"
          />
          <div v-else class="sm:col-span-3" />
          <div class="flex items-center justify-between gap-2 sm:col-span-2">
            <USwitch
              :model-value="Boolean(item.required)"
              size="sm"
              @update:model-value="updateColumn(item.id, { required: Boolean($event) })"
            />
            <UButton
              icon="i-lucide-trash-2"
              color="error"
              variant="ghost"
              size="xs"
              @click="removeColumn(item.id)"
            />
          </div>
        </div>
      </template>
      <template #empty>
        {{ t('docetra.config.noTableColumns') }}
      </template>
    </CommonAppSortableList>
  </div>
</template>
