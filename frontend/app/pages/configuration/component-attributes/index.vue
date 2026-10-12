<script setup lang="ts">
import type { ComponentAttribute, ComponentDataType } from '~/types/component-config'
import type { SaveGridChange } from '~/types/save-grid'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import {
  componentAttributeColumns,
  componentAttributePayload,
  componentAttributeRows,
  componentConfigTable,
  componentDataTypeItems,
} from '~/utils/freight/component-config-tables'

definePageMeta({
  titleKey: 'freight.pages.componentAttributes',
  permission: 'configuration.manage',
})

type AttributeDataType = Exclude<ComponentDataType, 'reference'>

type AttributeDraft = {
  label: string
  dataType: AttributeDataType
  isRequired: boolean
  helpText: string
}

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()

const slugify = (value: string) => value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')

/**
 * Rows the grid edits. Kept locally so a cell edit is stored until Save;
 * `syncRows` reseeds it from the API after every save. Creation happens in a
 * dialog instead of a blank grid row.
 */
const gridRows = ref<Array<Record<string, unknown>>>([])

const table = computed(() => componentConfigTable({
  key: 'componentAttributes',
  title: t('freight.pages.componentAttributes'),
  hideTitle: true,
  hideAddRow: true,
  columns: componentAttributeColumns().map(column => (column.key === 'dataType'
    ? { ...column, optionItems: componentDataTypeItems() }
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

// --- Create dialog -----------------------------------------------------------
const dialogOpen = ref(false)
const draft = ref<AttributeDraft>({
  label: '',
  dataType: 'text',
  isRequired: false,
  helpText: '',
})

function startAdd() {
  draft.value = { label: '', dataType: 'text', isRequired: false, helpText: '' }
  dialogOpen.value = true
}

async function submitAdd() {
  const payload = componentAttributePayload({ ...draft.value } as Record<string, unknown>, slugify(draft.value.label))
  if (!payload.label) {
    toast.add({ title: 'Label is required.', color: 'error' })
    return
  }
  try {
    await config.createAttribute(payload)
    dialogOpen.value = false
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    await config.loadAttributes(true)
    syncRows()
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function remove(attribute: ComponentAttribute) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.deleteComponentConfirm', descriptionParams: { name: attribute.label } })
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
      // `code` is immutable once created, so edits keep it.
      if (saved) await config.updateAttribute(id, { ...payload, code: saved.code })
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

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      title="Add attribute"
      :saving="config.saving.value"
      confirm-label="Create"
      @confirm="submitAdd"
    >
      <div class="space-y-4">
        <UFormField label="Label" required>
          <UInput
            v-model="draft.label"
            placeholder="e.g. Container No."
            class="w-full"
          />
        </UFormField>
        <UFormField label="Type">
          <USelect
            v-model="draft.dataType"
            :items="componentDataTypeItems()"
            class="w-full"
          />
        </UFormField>
        <UFormField label="Help text" help="Shown below the field to guide the user.">
          <UInput
            v-model="draft.helpText"
            placeholder="e.g. Enter the shipping container number"
            class="w-full"
          />
        </UFormField>
        <UCheckbox v-model="draft.isRequired" label="Required" />
      </div>
    </CommonAppEntityDialog>
  </div>
</template>
