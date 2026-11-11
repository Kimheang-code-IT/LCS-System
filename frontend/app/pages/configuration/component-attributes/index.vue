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
import type { ComponentAttributeInput, ComponentReferenceType } from '~/types/component-config'
import {
  attributeTypeIsReference,
  attributeTypeSupportsChoices,
  blankComponentAttributeRow,
  componentAttributeColumns,
  componentAttributePayload,
  componentAttributeRows,
  componentAttributeToRow,
  componentConfigTable,
  componentDataTypeItems,
  componentReferenceTypeItems,
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
  code: 'Code',
  label: 'Label',
  dataType: 'Data Type',
  options: 'Choices',
  referenceType: 'Master Data',
  validationRules: 'Rules',
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

/**
 * Settings that no longer have a visible column; they live in the row's
 * settings dialog (`ComponentAttributeSettingsDialog` below). A refusal on one
 * of them must surface there or as form text, never on an invisible cell.
 */
const SETTINGS_FIELD_KEYS = ['options', 'referenceType', 'validationRules', 'helpText'] as AttributeFieldKey[]

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

/** Codes held by the other rows, for the in-grid duplicate check. */
function otherCodes(id: string): string[] {
  return rows.value
    .filter(row => String(row.id ?? '') !== id)
    .map(row => String(row.code ?? ''))
    .filter(Boolean)
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
  // Wait for UTable to paint the new row before placing the caret in Code.
  await nextTick()
  await focusField(attributeCellKey(index, 'code'))
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
  if (change.key !== 'dataType' && change.key !== 'isRequired' && change.key !== 'referenceType') return
  const id = String(row.id ?? '')
  void nextTick(() => queueFieldSave(id, change.key as AttributeFieldKey))
}

function onCellBlur(_cellKey: string, change: { index: number, key: string }) {
  const row = rows.value[change.index]
  if (!row || isSaveGridNewRow(row) || !isAttributeFieldKey(change.key)) return
  if (change.key === 'dataType' || change.key === 'isRequired' || change.key === 'referenceType') return

  const id = String(row.id ?? '')
  const trimmed = String(row[change.key] ?? '').trim()
  if (trimmed !== row[change.key]) patchRow(id, { [change.key]: trimmed })

  const current = { ...row, [change.key]: trimmed }
  const issue = attributeFieldIssue(change.key, current, otherCodes(id))
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

  // A data type change is only valid together with its dependent settings:
  // select needs choices, reference needs a Master Data source. Refuse it
  // before the request and leave the typed value in place on the failing cell.
  // The dependent settings have no visible cell, so the refusal is form text
  // pointing at the row's settings dialog.
  if (key === 'dataType') {
    const dependent = (['options', 'referenceType'] as AttributeFieldKey[])
      .find(candidate => attributeFieldIssue(candidate, row))
    if (dependent) {
      patchRow(id, { dataType: saved.dataType })
      formErrors.value = [
        `${FIELD_LABELS[dependent]} is required for this data type — open Edit settings for the row first.`,
      ]
      return
    }
  }

  const issue = attributeFieldIssue(key, row, otherCodes(id))
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
    if (!mapped.isValidation || key === 'isRequired' || key === 'dataType' || key === 'referenceType') {
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
  const nextRow = {
    ...row,
    label,
    // A blank code keeps the pre-existing convenience of deriving one from the
    // label; the value is shown and editable in its own column before saving.
    code: String(row.code ?? '').trim() || slugify(label),
    helpText,
    dataType: attributeFieldValue('dataType', row),
    referenceType: attributeFieldValue('referenceType', row),
    options: String(row.options ?? '').trim(),
    validationRules: String(row.validationRules ?? '').trim(),
  }

  const fields: AttributeFieldKey[] = [
    'code',
    'label',
    'dataType',
    'options',
    'referenceType',
    'validationRules',
    'helpText',
  ]
  const codes = otherCodes(id)
  const errors: Record<string, string> = {}
  const hiddenIssues: string[] = []
  for (const key of fields) {
    const issue = attributeFieldIssue(key, nextRow, codes)
    if (!issue) continue
    // Settings fields have no visible cell; listing them as form text (with the
    // dialog as the fix) beats an error tag the user cannot see.
    if ((SETTINGS_FIELD_KEYS as AttributeFieldKey[]).includes(key)) {
      hiddenIssues.push(`${FIELD_LABELS[key]}: ${issueText(issue, key)}`)
      continue
    }
    errors[attributeCellKey(index, key)] = issueText(issue, key)
  }
  if (Object.keys(errors).length) {
    fieldErrors.value = { ...fieldErrors.value, ...errors }
    const firstKey = fields.find(key => attributeCellKey(index, key) in errors) || 'label'
    await nextTick()
    await focusField(attributeCellKey(index, firstKey))
    return
  }
  if (hiddenIssues.length) {
    formErrors.value = [
      'This attribute needs settings before it can be saved — use Edit on the row:',
      ...hiddenIssues,
    ]
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
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

// --- Row settings dialog -----------------------------------------------------
// Choices, Master Data, Display Order, Rules and Help Text have no column in
// the compact table; this dialog edits them for one row, new or saved.
const settingsOpen = ref(false)
const settingsRowId = ref('')
const settingsForm = ref<{
  options: string
  referenceType: ComponentReferenceType | ''
  validationRules: string
  helpText: string
  displayOrder: number
}>({
  options: '',
  referenceType: '',
  validationRules: '',
  helpText: '',
  displayOrder: 0,
})
const settingsErrors = ref<Record<string, string>>({})
const settingsSaving = ref(false)

const settingsRow = computed(() => rows.value.find(row => String(row.id ?? '') === settingsRowId.value) || null)
/** Type-specific settings follow the row's own data type, not a hardcoded list. */
const settingsShowChoices = computed(() => attributeTypeSupportsChoices(settingsRow.value?.dataType))
const settingsShowReference = computed(() => attributeTypeIsReference(settingsRow.value?.dataType))
const settingsReferenceItems = componentReferenceTypeItems()

function openSettings(row: AttributeRow) {
  settingsRowId.value = String(row.id ?? '')
  settingsForm.value = {
    options: String(row.options ?? ''),
    referenceType: (typeof row.referenceType === 'string' && row.referenceType
      ? row.referenceType
      : '') as ComponentReferenceType | '',
    validationRules: String(row.validationRules ?? ''),
    helpText: String(row.helpText ?? ''),
    displayOrder: Number(row.displayOrder ?? 0),
  }
  settingsErrors.value = {}
  settingsOpen.value = true
}

function saveSettingsRow() {
  const row = settingsRow.value
  const id = settingsRowId.value
  if (!row || !id || settingsSaving.value) return
  void applySettings(row, id)
}

async function applySettings(row: AttributeRow, id: string) {
  const form = { ...settingsForm.value, options: settingsForm.value.options.trim() }

  // Visible settings validate against the same field rules the inline cells
  // used, so a select without choices or a reference without master data is
  // refused here exactly as it was refused in the grid.
  const errors: Record<string, string> = {}
  for (const key of SETTINGS_FIELD_KEYS) {
    if (key === 'options' && !settingsShowChoices.value) continue
    if (key === 'referenceType' && !settingsShowReference.value) continue
    const issue = attributeFieldIssue(key, { ...row, ...form })
    if (issue) errors[key] = issueText(issue, key)
  }
  if (Object.keys(errors).length) {
    settingsErrors.value = errors
    return
  }

  // An unsaved row has nothing to PATCH: stage the settings on the row; the
  // grid's Save button then persists them with the existing full payload.
  if (isSaveGridNewRow(row)) {
    patchRow(id, form)
    settingsErrors.value = {}
    settingsOpen.value = false
    return
  }

  const saved = persisted.value[id]
  if (!saved) return
  const candidate = { ...row, ...form }
  // Send only what changed, one PATCH: the per-field inline editor must never
  // race a stale dialog write over the same field.
  const payload: Partial<ComponentAttributeInput> = {}
  for (const key of SETTINGS_FIELD_KEYS) {
    if (key === 'options' && !settingsShowChoices.value) continue
    if (key === 'referenceType' && !settingsShowReference.value) continue
    const value = attributeFieldValue(key, candidate)
    if (sameAttributeFieldValue(key, value, saved[key])) continue
    Object.assign(payload, attributeFieldPayload(key, candidate))
  }
  if (Number(row.displayOrder ?? 0) !== Number(form.displayOrder)) {
    payload.displayOrder = Number(form.displayOrder)
  }
  if (!Object.keys(payload).length) {
    settingsOpen.value = false
    return
  }

  settingsSaving.value = true
  try {
    const updated = await config.updateAttribute(id, payload)
    const canonical = componentAttributeToRow(updated)
    rows.value = rows.value.map(item => (String(item.id ?? '') === id ? { ...item, ...canonical } : item))
    persisted.value = { ...persisted.value, [id]: canonical }
    settingsErrors.value = {}
    settingsOpen.value = false
    formErrors.value = []
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    // Display order sorts the server list; re-read so the rows match what the
    // grid would show on the next visit.
    if (payload.displayOrder !== undefined) await refresh()
  }
  catch (error) {
    const mapped = attributeServerError(error, rowIndex(id))
    for (const [cellKey, message] of Object.entries(mapped.fieldErrors)) {
      const key = (cellKey.split('.').pop() || '') as AttributeFieldKey
      if ((SETTINGS_FIELD_KEYS as AttributeFieldKey[]).includes(key)) {
        settingsErrors.value = { ...settingsErrors.value, [key]: message }
      }
      else {
        fieldErrors.value = { ...fieldErrors.value, [cellKey]: message }
      }
    }
    if (mapped.message) formErrors.value = [mapped.message]
  }
  finally {
    settingsSaving.value = false
  }
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

// --- Reorder -----------------------------------------------------------------
/** Persist the catalog order after the grid's move buttons reorder the rows. */
async function reorderRows(next: AttributeRow[]) {
  // An unsaved row has no server id and must keep its typed values; refusing
  // the move is better than reloading the page and losing them.
  if (next.some(isSaveGridNewRow)) {
    formErrors.value = ['Save or cancel the new attribute before changing the order.']
    return
  }
  const ids = next.map(row => String(row.id ?? '')).filter(Boolean)
  if (!ids.length) return
  clearAllCellErrors()
  try {
    formErrors.value = []
    await config.reorderAttributes(ids)
  }
  catch (error) {
    formErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
    await refresh()
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
        label: t('actions.edit'),
        icon: 'i-lucide-settings-2',
        disabled: saving,
        onSelect: () => openSettings(row),
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
      label: t('actions.edit'),
      icon: 'i-lucide-settings-2',
      disabled: saving,
      onSelect: () => openSettings(row),
    },
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
      :refreshing="config.loading.value"
      @create="startAdd"
      @refresh="refresh"
    >
      <ExcelConfigPageIo
        collection="componentAttributes"
        @imported="refresh"
      />
    </LayoutAppHeaderPageActions>

    <CommonAppFormErrorSummary class="mb-2" :form-errors="formErrors" />

    <div
      v-if="config.loading.value && !rows.length"
      class="flex items-center gap-2 text-sm text-muted"
      role="status">
      <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin" />
      Loading attributes…
    </div>

    <FreightAppLineTable
      :table="table"
      :model-value="rows"
      :field-errors="fieldErrors"
      :row-disabled="rowDisabled"
      :row-inline-actions="rowInlineActions"
      :on-cell-edit="onCellEdit"
      :on-cell-blur="onCellBlur"
      :on-reorder="reorderRows"
      @update:model-value="rows = $event" />

    <UModal v-model:open="settingsOpen" title="Attribute settings" :ui="{ content: 'max-w-xl' }">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="text-base font-semibold">
              {{ settingsRow?.label || 'Attribute settings' }}
            </h3>
            <p class="text-sm text-muted">
              Code {{ settingsRow?.code || '—' }} · Data type {{ String(settingsRow?.dataType ?? '').replace(/_/g, ' ') }}
            </p>
          </template>

          <div class="space-y-4">
            <UFormField
              v-if="settingsShowChoices"
              label="Choices (a, b)"
              :error="settingsErrors.options"
              hint="Comma separated; Label|Value for a custom value."
            >
              <UInput
                v-model="settingsForm.options"
                size="sm"
                maxlength="1000"
                class="w-full"
                placeholder="Open, Closed|C"
              />
            </UFormField>

            <UFormField
              v-if="settingsShowReference"
              label="Master Data"
              :error="settingsErrors.referenceType"
            >
              <USelect
                :model-value="settingsForm.referenceType || undefined"
                :items="settingsReferenceItems"
                size="sm"
                class="w-full"
                placeholder="Choose the referenced records"
                @update:model-value="settingsForm.referenceType = ((typeof $event === 'string' && $event)
                  ? $event
                  : '') as ComponentReferenceType | ''"
              />
            </UFormField>

            <p class="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Advanced settings
            </p>
            <div class="grid gap-3 sm:grid-cols-2">
              <UFormField label="Display Order" hint="Position in the catalog list.">
                <UInputNumber
                  v-model="settingsForm.displayOrder"
                  size="sm"
                  :min="0"
                  :step="1"
                  class="w-full"
                />
              </UFormField>
              <UFormField label="Help Text" :error="settingsErrors.helpText">
                <UInput
                  v-model="settingsForm.helpText"
                  size="sm"
                  maxlength="255"
                  class="w-full"
                  placeholder="Shown under the field"
                />
              </UFormField>
            </div>
            <UFormField label="Validation Rules (key=value)" :error="settingsErrors.validationRules">
              <UInput
                v-model="settingsForm.validationRules"
                size="sm"
                maxlength="500"
                class="w-full"
                placeholder="min=0; max=100"
              />
            </UFormField>
          </div>

          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                :disabled="settingsSaving"
                @click="settingsOpen = false"
              >
                {{ t('actions.cancel') }}
              </UButton>
              <UButton
                color="primary"
                icon="i-lucide-check"
                :loading="settingsSaving"
                :disabled="settingsSaving"
                @click="saveSettingsRow"
              >
                {{ t('actions.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
