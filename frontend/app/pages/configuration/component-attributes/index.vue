<script setup lang="ts">
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import { createClientId } from '~/utils/client-id'
import { isSaveGridNewRow, SAVE_GRID_NEW_PREFIX } from '~/types/save-grid'
import {
  attributeCellKey,
  attributeFieldIssue,
  attributeFieldPayload,
  attributeFieldValue,
  attributeServerError,
  isAttributeFieldKey,
  sameAttributeFieldValue,
  type AttributeFieldKey,
} from '~/utils/freight/component-attribute-inline'
import {
  blankComponentAttributeRow,
  componentAttributeColumns,
  componentAttributePayload,
  componentAttributeRows,
  componentAttributeToRow,
  componentConfigTable,
  componentDataTypeItems,
} from '~/utils/freight/component-config-tables'
import { focusField } from '~/utils/validation/focus'
import { failureMessage } from '~/utils/validation/messages'
import { apiErrorMessage } from '~/utils/validation/api-error'

definePageMeta({
  titleKey: 'freight.pages.componentAttributes',
  permission: 'configuration.manage',
})

type AttributeRow = Record<string, unknown>

/** Labels used by the shared validation wording; the grid's own headers match. */
const FIELD_LABELS: Record<AttributeFieldKey, string> = {
  label: 'Label',
  dataType: 'Data Type',
  isRequired: 'Required',
  helpText: 'Help Text',
}

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()

/** Rows the grid edits. New rows carry a `new_` id until the API returns one. */
const rows = ref<AttributeRow[]>([])
/** Last server-confirmed value per row, used to skip no-op PATCHes and to undo a failed one. */
const persisted = ref<Record<string, AttributeRow>>({})
/** Cell errors keyed `componentAttributes.<rowIndex>.<column>`. */
const fieldErrors = ref<Record<string, string>>({})
/** Refusals that belong to no single cell. */
const formErrors = ref<string[]>([])

/** One serial queue per saved row: edits are applied in order, never in parallel. */
const saveQueues = new Map<string, Promise<void>>()

const table = computed(() => componentConfigTable({
  key: 'componentAttributes',
  title: t('freight.pages.componentAttributes'),
  hideTitle: true,
  hideAddRow: true,
  columns: componentAttributeColumns().map(column => (column.key === 'dataType'
    ? { ...column, optionItems: componentDataTypeItems() }
    : column)),
}))

function rowIndex(id: string): number {
  return rows.value.findIndex(row => String(row.id ?? '') === id)
}

function patchRow(id: string, patch: AttributeRow) {
  rows.value = rows.value.map(row => (String(row.id ?? '') === id ? { ...row, ...patch } : row))
}

function setCellError(index: number, key: AttributeFieldKey, message: string) {
  fieldErrors.value = { ...fieldErrors.value, [attributeCellKey(index, key)]: message }
}

function clearCellError(index: number, key: AttributeFieldKey) {
  const cellKey = attributeCellKey(index, key)
  if (!(cellKey in fieldErrors.value)) return
  fieldErrors.value = Object.fromEntries(
    Object.entries(fieldErrors.value).filter(([existing]) => existing !== cellKey),
  )
}

function clearAllCellErrors() {
  fieldErrors.value = {}
}

function issueText(issue: ReturnType<typeof attributeFieldIssue>, key: AttributeFieldKey): string {
  return issue ? failureMessage(t, { ...issue, label: FIELD_LABELS[key] }) : ''
}

function syncRows() {
  const projected = componentAttributeRows(config.attributes.value)
  rows.value = projected.map(row => ({ ...row, _saving: false }))
  persisted.value = Object.fromEntries(projected.map(row => [String(row.id), { ...row }]))
  clearAllCellErrors()
  formErrors.value = []
}

async function refresh() {
  formErrors.value = []
  await config.loadAttributes(true)
  syncRows()
}

onMounted(refresh)

// --- Add / cancel a new row --------------------------------------------------
async function startAdd() {
  const id = createClientId(SAVE_GRID_NEW_PREFIX)
  rows.value = [...rows.value, { ...blankComponentAttributeRow(), id, _saving: false }]
  clearAllCellErrors()
  const index = rows.value.length - 1
  // Wait for UTable to paint the new row before placing the caret in Label.
  await nextTick()
  await focusField(attributeCellKey(index, 'label'))
}

function cancelNew(id: string) {
  rows.value = rows.value.filter(row => String(row.id ?? '') !== id)
  clearAllCellErrors()
}

// --- Edit / save an existing row --------------------------------------------
/**
 * Cell edits arrive before the renderer applies the new value, so immediate
 * commits wait one tick. Text cells commit on blur instead, not per keystroke.
 */
function onCellEdit(_cellKey: string, change?: { index: number, key: string, value: unknown }) {
  if (!change) return
  if (isAttributeFieldKey(change.key)) clearCellError(change.index, change.key)
  const row = rows.value[change.index]
  if (!row || isSaveGridNewRow(row) || !isAttributeFieldKey(change.key)) return
  if (change.key !== 'dataType' && change.key !== 'isRequired') return
  const id = String(row.id ?? '')
  void nextTick(() => queueFieldSave(id, change.key as AttributeFieldKey))
}

function onCellBlur(_cellKey: string, change: { index: number, key: string }) {
  const row = rows.value[change.index]
  if (!row || isSaveGridNewRow(row) || !isAttributeFieldKey(change.key)) return
  if (change.key !== 'label' && change.key !== 'helpText') return

  const id = String(row.id ?? '')
  const trimmed = String(row[change.key] ?? '').trim()
  if (trimmed !== row[change.key]) patchRow(id, { [change.key]: trimmed })

  const current = { ...row, [change.key]: trimmed }
  const issue = attributeFieldIssue(change.key, current)
  if (issue) {
    setCellError(change.index, change.key, issueText(issue, change.key))
    void focusField(attributeCellKey(change.index, change.key))
    return
  }
  clearCellError(change.index, change.key)
  queueFieldSave(id, change.key)
}

function queueFieldSave(id: string, key: AttributeFieldKey) {
  const previous = saveQueues.get(id) ?? Promise.resolve()
  const task = previous.then(
    () => persistField(id, key),
    () => persistField(id, key),
  )
  saveQueues.set(id, task)
  void task.finally(() => {
    if (saveQueues.get(id) === task) saveQueues.delete(id)
  })
}

async function persistField(id: string, key: AttributeFieldKey) {
  const index = rowIndex(id)
  if (index < 0) return
  const row = rows.value[index]!
  if (isSaveGridNewRow(row)) return

  const saved = persisted.value[id]
  if (!saved) return

  const value = attributeFieldValue(key, row)
  // A queued edit may already have been saved by the task ahead of it.
  if (sameAttributeFieldValue(key, value, saved[key])) {
    clearCellError(index, key)
    return
  }

  const issue = attributeFieldIssue(key, row)
  if (issue) {
    setCellError(index, key, issueText(issue, key))
    return
  }

  patchRow(id, { _saving: true })
  try {
    const updated = await config.updateAttribute(id, attributeFieldPayload(key, row))
    formErrors.value = []
    const canonical = componentAttributeToRow(updated)
    persisted.value = {
      ...persisted.value,
      [id]: { ...saved, [key]: canonical[key] },
    }

    const latestIndex = rowIndex(id)
    const latest = latestIndex >= 0 ? rows.value[latestIndex]! : null
    // Never overwrite a newer edit that arrived while this request was open.
    if (latest && sameAttributeFieldValue(key, latest[key], value)) {
      patchRow(id, { [key]: canonical[key] })
    }
    clearCellError(latestIndex >= 0 ? latestIndex : index, key)
  }
  catch (error) {
    const errorIndex = Math.max(rowIndex(id), index)
    const mapped = attributeServerError(error, errorIndex)
    fieldErrors.value = { ...fieldErrors.value, ...mapped.fieldErrors }
    if (mapped.message) formErrors.value = [mapped.message]

    // A checkbox or dropdown cannot carry an invalid value forward, and a
    // transport/server failure means the edit never happened: put the last
    // confirmed value back. A validation refusal on free text stays visible so
    // the user can correct what they typed.
    if (!mapped.isValidation || key === 'isRequired' || key === 'dataType') {
      patchRow(id, { [key]: saved[key] })
    }
  }
  finally {
    patchRow(id, { _saving: false })
  }
}

// --- Save a new row ----------------------------------------------------------
async function saveNewRow(row: AttributeRow) {
  const id = String(row.id ?? '')
  if (!id || row._saving) return

  const index = rowIndex(id)
  if (index < 0) return

  const label = String(row.label ?? '').trim()
  const helpText = String(row.helpText ?? '').trim()
  const nextRow = { ...row, label, helpText, dataType: attributeFieldValue('dataType', row) }

  const errors: Record<string, string> = {}
  for (const key of ['label', 'dataType', 'helpText'] as AttributeFieldKey[]) {
    const issue = attributeFieldIssue(key, nextRow)
    if (issue) errors[attributeCellKey(index, key)] = issueText(issue, key)
  }
  if (Object.keys(errors).length) {
    fieldErrors.value = { ...fieldErrors.value, ...errors }
    const firstKey = (['label', 'dataType', 'helpText'] as AttributeFieldKey[])
      .find(key => attributeCellKey(index, key) in errors) || 'label'
    await nextTick()
    await focusField(attributeCellKey(index, firstKey))
    return
  }

  patchRow(id, { ...nextRow, _saving: true })
  try {
    const created = await config.createAttribute(componentAttributePayload(nextRow, slugify(label)))
    const createdRow = componentAttributeToRow(created)
    rows.value = rows.value.map(item => (
      String(item.id ?? '') === id ? { ...createdRow, _saving: false } : item
    ))
    persisted.value = { ...persisted.value, [created.id]: { ...createdRow } }
    clearAllCellErrors()
    formErrors.value = []
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    const mapped = attributeServerError(error, index)
    fieldErrors.value = { ...fieldErrors.value, ...mapped.fieldErrors }
    if (mapped.message) formErrors.value = [mapped.message]
    patchRow(id, { _saving: false })
  }
}

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

// --- Delete ------------------------------------------------------------------
async function removeExisting(id: string) {
  const row = rows.value.find(item => String(item.id ?? '') === id)
  const attribute = config.attributes.value.find(item => item.id === id)
  if (!row || !attribute) return

  // A blurred Label/Help Text edit may still be in flight; deleting first would
  // race it and bring the row back on refresh.
  const pending = saveQueues.get(id)
  if (pending) await pending

  const accepted = await confirm({
    kind: 'delete',
    descriptionKey: 'freight.ui.deleteComponentConfirm',
    descriptionParams: { name: attribute.label },
  })
  if (!accepted) return

  try {
    const result = await config.deleteAttribute(id)
    if (result.archived) {
      toast.add({ title: t('freight.ui.archived'), color: 'warning' })
      return
    }
    rows.value = rows.value.filter(item => String(item.id ?? '') !== id)
    persisted.value = Object.fromEntries(
      Object.entries(persisted.value).filter(([rowId]) => rowId !== id),
    )
    clearAllCellErrors()
    toast.add({ title: t('actions.delete'), color: 'success' })
  }
  catch (error) {
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

// --- Grid wiring -------------------------------------------------------------
function rowDisabled(row: AttributeRow) {
  return Boolean(row._saving)
}

function rowInlineActions(row: AttributeRow) {
  const id = String(row.id ?? '')
  const saving = Boolean(row._saving)
  if (isSaveGridNewRow(row)) {
    return [
      {
        label: t('actions.save'),
        icon: 'i-lucide-check',
        color: 'primary' as const,
        loading: saving,
        disabled: saving,
        onSelect: () => void saveNewRow(row),
      },
      {
        label: t('actions.cancel'),
        icon: 'i-lucide-x',
        disabled: saving,
        onSelect: () => cancelNew(id),
      },
    ]
  }
  return [
    // A field save has no explicit Save button, so show its progress in the
    // Actions cell until the PATCH settles.
    ...(saving
      ? [{
          label: t('actions.save'),
          icon: 'i-lucide-save',
          loading: true,
          disabled: true,
          onSelect: () => {},
        }]
      : []),
    {
      label: t('actions.delete'),
      icon: 'i-lucide-trash-2',
      color: 'error' as const,
      disabled: saving,
      onSelect: () => void removeExisting(id),
    },
  ]
}
</script>

<template>
  <div class="mx-auto flex w-[95%] max-w-[1800px] flex-col gap-4 p-4">
    <LayoutAppHeaderPageActions
      can-create
      create-label="Add attribute"
      @create="startAdd"
      @refresh="refresh"
    />

    <CommonAppFormErrorSummary class="mb-2" :form-errors="formErrors" />

    <FreightAppLineTable
      :table="table"
      :model-value="rows"
      :field-errors="fieldErrors"
      :row-disabled="rowDisabled"
      :row-inline-actions="rowInlineActions"
      :on-cell-edit="onCellEdit"
      :on-cell-blur="onCellBlur"
      @update:model-value="rows = $event" />
  </div>
</template>
