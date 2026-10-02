<script setup lang="ts">
import type { ComponentAttribute } from '~/types/component-config'
import type { SaveGridChange } from '~/types/save-grid'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import {
  blankComponentAttributeRow,
  componentAttributeColumns,
  componentAttributePayload,
  componentAttributeRows,
  componentConfigTable,
  componentDataTypeItems,
  componentReferenceTypeItems,
} from '~/utils/freight/component-config-tables'
import { createClientId } from '~/utils/client-id'

definePageMeta({
  titleKey: 'freight.pages.componentAttributes',
  permission: 'configuration.manage',
})

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()

const slugify = (value: string) => value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

/**
 * Rows the grid edits. Kept locally so "Add attribute" and a cell edit are the
 * same kind of change; `syncRows` reseeds it from the API after every save.
 */
const gridRows = ref<Array<Record<string, unknown>>>([])

const table = computed(() => componentConfigTable({
  key: 'componentAttributes',
  title: t('freight.pages.componentAttributes'),
  columns: componentAttributeColumns().map(column => (column.key === 'dataType'
    ? { ...column, optionItems: componentDataTypeItems() }
    : column.key === 'referenceType'
      ? { ...column, optionItems: componentReferenceTypeItems() }
      : column)),
}))

function syncRows() {
  gridRows.value = componentAttributeRows(config.attributes.value)
}

async function refresh() {
  await config.loadAttributes(true)
  syncRows()
}

onMounted(refresh)

function startAdd() {
  gridRows.value = [{ ...blankComponentAttributeRow(), id: createClientId('new') }, ...gridRows.value]
}

async function remove(attribute: ComponentAttribute) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.delete', descriptionParams: { name: attribute.label } })
  if (!accepted) return false
  const result = await config.deleteAttribute(attribute.id)
  toast.add({ title: result.archived ? t('freight.ui.archived') : t('actions.delete'), color: result.archived ? 'warning' : 'success' })
  return true
}

async function save(change: SaveGridChange) {
  const savedById = new Map(config.attributes.value.map(attribute => [attribute.id, attribute]))
  try {
    for (const id of change.removedIds) {
      const attribute = savedById.get(id)
      if (attribute) await remove(attribute)
    }
    for (const row of change.rows) {
      const id = String(row.id ?? '')
      const saved = savedById.get(id)
      const payload = componentAttributePayload(row, slugify(String(row.label ?? '')))
      if (!payload.label) continue
      // `code` is immutable once created, so new rows send it and edits keep it.
      if (saved) await config.updateAttribute(id, { ...payload, code: saved.code })
      else await config.createAttribute(payload)
    }
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    await config.loadAttributes(true)
    syncRows()
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
    await config.loadAttributes(true)
    syncRows()
  }
}
</script>

<template>
  <div class="mx-auto flex w-full max-w-5xl flex-col gap-4 p-4">
    <LayoutAppHeaderPageActions
      can-create
      create-label="Add attribute"
      @create="startAdd"
      @refresh="refresh"
    />

    <TableAppSaveGrid
      :table="table"
      :rows="gridRows"
      :saving="config.saving.value"
      @save="save" />
  </div>
</template>