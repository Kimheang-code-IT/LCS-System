<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type {
  DynamicColumnInput,
  DynamicFieldType,
  DynamicReferenceType,
  DynamicTabColumn,
} from '~/types/freight/dynamic-tabs'
import { DYNAMIC_FIELD_TYPES, DYNAMIC_REFERENCE_TYPES } from '~/types/freight/dynamic-tabs'
import { useServiceOrderTabConfig } from '~/composables/freight/useServiceOrderTabConfig'
import { useConfirm } from '~/composables/common/useConfirm'

definePageMeta({
  titleKey: 'freight.pages.serviceOrderTabs',
  permission: 'configuration.manage',
})

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useServiceOrderTabConfig()

const tabModalOpen = ref(false)
const columnModalOpen = ref(false)
const showArchived = ref(false)

const tabForm = reactive({
  id: '',
  name: '',
  code: '',
  icon: 'i-lucide-table',
  sortOrder: 10,
  isActive: true,
  allowMultipleRows: true,
})

const columnForm = reactive({
  id: '',
  label: '',
  fieldKey: '',
  fieldType: 'text' as DynamicFieldType,
  referenceType: undefined as DynamicReferenceType | undefined,
  isRequired: false,
  isActive: true,
  showInSummary: false,
  width: '',
  placeholder: '',
  defaultValue: '',
  optionsText: '',
  keyTouched: false,
})

const visibleColumns = computed(() =>
  config.columns.value.filter(column => showArchived.value || !column.isArchived),
)

const typeItems = DYNAMIC_FIELD_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
const referenceItems = DYNAMIC_REFERENCE_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
const needsOptions = computed(() => ['select', 'multi_select', 'currency'].includes(columnForm.fieldType))

const columnTableColumns: TableColumn<DynamicTabColumn>[] = [
  { id: 'order', header: '#' },
  { accessorKey: 'label', header: 'Column' },
  { accessorKey: 'fieldType', header: 'Type' },
  { accessorKey: 'referenceType', header: 'Reference' },
  { accessorKey: 'isRequired', header: 'Required' },
  { accessorKey: 'isActive', header: 'Active' },
  { id: 'actions', header: '' },
]

onMounted(() => { void config.loadTabs(true) })

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

watch(() => columnForm.label, (label) => {
  if (!columnForm.id && !columnForm.keyTouched) columnForm.fieldKey = slugify(label)
})

function openCreateTab() {
  Object.assign(tabForm, { id: '', name: '', code: '', icon: 'i-lucide-table', sortOrder: (config.tabs.value.length + 1) * 10, isActive: true, allowMultipleRows: true })
  tabModalOpen.value = true
}

function openEditTab(id: string) {
  const tab = config.tabs.value.find(row => row.id === id)
  if (!tab) return
  Object.assign(tabForm, {
    id: tab.id,
    name: tab.name,
    code: tab.code,
    icon: tab.icon || 'i-lucide-table',
    sortOrder: tab.sortOrder,
    isActive: tab.isActive,
    allowMultipleRows: tab.allowMultipleRows,
  })
  tabModalOpen.value = true
}

async function saveTab() {
  if (!tabForm.name.trim()) return
  try {
    if (tabForm.id) {
      await config.updateTab(tabForm.id, { name: tabForm.name, icon: tabForm.icon, sortOrder: Number(tabForm.sortOrder), isActive: tabForm.isActive, allowMultipleRows: tabForm.allowMultipleRows })
    }
    else {
      await config.createTab({ name: tabForm.name, code: tabForm.code || slugify(tabForm.name).replace(/_/g, '-'), icon: tabForm.icon, sortOrder: Number(tabForm.sortOrder), isActive: tabForm.isActive, allowMultipleRows: tabForm.allowMultipleRows })
    }
    tabModalOpen.value = false
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function removeTab(id: string) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.delete', descriptionParams: { name: config.tabs.value.find(row => row.id === id)?.name || '' } })
  if (!accepted) return
  const result = await config.deleteTab(id)
  toast.add({ title: result.archived ? t('freight.ui.archived') : t('actions.delete'), color: result.archived ? 'warning' : 'success' })
}

async function moveTab(id: string, direction: -1 | 1) {
  const tabs = config.tabs.value
  const index = tabs.findIndex(row => row.id === id)
  const target = index + direction
  if (index < 0 || target < 0 || target >= tabs.length) return
  const reordered = [...tabs]
  const [item] = reordered.splice(index, 1)
  reordered.splice(target, 0, item!)
  for (const [position, tab] of reordered.entries()) {
    if (tab.sortOrder !== (position + 1) * 10) await config.updateTab(tab.id, { sortOrder: (position + 1) * 10 })
  }
}

function openCreateColumn() {
  Object.assign(columnForm, { id: '', label: '', fieldKey: '', fieldType: 'text', referenceType: undefined, isRequired: false, isActive: true, showInSummary: false, width: '', placeholder: '', defaultValue: '', optionsText: '', keyTouched: false })
  columnModalOpen.value = true
}

function openEditColumn(id: string) {
  const column = config.columns.value.find(row => row.id === id)
  if (!column) return
  Object.assign(columnForm, {
    id: column.id,
    label: column.label,
    fieldKey: column.fieldKey,
    fieldType: column.fieldType,
    referenceType: column.referenceType || undefined,
    isRequired: column.isRequired,
    isActive: column.isActive,
    showInSummary: column.showInSummary,
    width: column.width || '',
    placeholder: column.placeholder || '',
    defaultValue: column.defaultValue || '',
    optionsText: (column.options || []).map(option => (typeof option === 'string' ? option : option.value)).join('\n'),
    keyTouched: true,
  })
  columnModalOpen.value = true
}

async function saveColumn() {
  if (!config.selectedTabId.value) return
  const payload: DynamicColumnInput = {
    label: columnForm.label,
    fieldKey: columnForm.fieldKey || slugify(columnForm.label),
    fieldType: columnForm.fieldType,
    referenceType: columnForm.fieldType === 'reference' ? (columnForm.referenceType || null) : null,
    isRequired: columnForm.isRequired,
    isActive: columnForm.isActive,
    showInSummary: columnForm.showInSummary,
    width: columnForm.width || undefined,
    placeholder: columnForm.placeholder || undefined,
    defaultValue: columnForm.defaultValue || undefined,
    options: needsOptions.value
      ? columnForm.optionsText.split('\n').map(line => line.trim()).filter(Boolean)
      : [],
  }
  try {
    if (columnForm.id) await config.updateColumn(columnForm.id, payload)
    else await config.createColumn(config.selectedTabId.value, payload)
    columnModalOpen.value = false
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function removeColumn(id: string) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.delete', descriptionParams: { name: config.columns.value.find(row => row.id === id)?.label || '' } })
  if (!accepted) return
  const result = await config.deleteColumn(id)
  toast.add({ title: result.archived ? t('freight.ui.archived') : t('actions.delete'), color: result.archived ? 'warning' : 'success' })
}

async function toggleColumn(id: string, value: boolean) {
  await config.updateColumn(id, { isActive: value })
}

async function moveColumn(id: string, direction: -1 | 1) {
  const columns = visibleColumns.value
  const index = columns.findIndex(row => row.id === id)
  const target = index + direction
  if (index < 0 || target < 0 || target >= columns.length) return
  const reordered = [...columns]
  const [item] = reordered.splice(index, 1)
  reordered.splice(target, 0, item!)
  await config.reorderColumns(config.selectedTabId.value, reordered.map(row => row.id))
}
</script>

<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-4 p-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-lg font-semibold text-highlighted">{{ t('freight.pages.serviceOrderTabs') }}</h1>
        <p class="text-sm text-muted">Configure the operational tabs shown on every Service Order. Each tab renders a dynamic editable table.</p>
      </div>
      <div class="flex items-center gap-2">
        <UCheckbox v-model="showArchived" label="Show archived" />
        <UButton icon="i-lucide-plus" color="primary" @click="openCreateTab">Add tab</UButton>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-[280px_1fr]">
      <aside class="rounded-lg border border-default bg-default p-2">
        <div class="flex items-center justify-between px-1 pb-2">
          <span class="text-xs font-semibold uppercase tracking-wide text-muted">Tabs</span>
          <UBadge color="neutral" variant="subtle" size="sm">{{ config.tabs.value.length }}</UBadge>
        </div>
        <div class="space-y-1">
          <button
            v-for="tab in config.tabs.value"
            :key="tab.id"
            type="button"
            class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition hover:bg-elevated"
            :class="tab.id === config.selectedTabId.value ? 'bg-elevated ring-1 ring-primary' : ''"
            @click="config.selectTab(tab.id)"
          >
            <UIcon :name="tab.icon || 'i-lucide-table'" class="size-4 shrink-0 text-muted" />
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="truncate font-medium text-highlighted">{{ tab.name }}</span>
              <span class="truncate text-[11px] text-muted">{{ tab.code }}</span>
            </span>
            <UBadge
v-if="tab.isArchived"
color="warning"
variant="subtle"
size="sm">archived</UBadge>
            <UBadge
v-else-if="!tab.isActive"
color="neutral"
variant="subtle"
size="sm">off</UBadge>
          </button>
        </div>
      </aside>

      <section class="rounded-lg border border-default bg-default p-3">
        <template v-if="config.selectedTabId.value">
          <div class="flex flex-wrap items-center justify-between gap-2 pb-3">
            <div class="flex items-center gap-2">
              <h2 class="text-base font-semibold text-highlighted">{{ config.tabs.value.find(tab => tab.id === config.selectedTabId.value)?.name }}</h2>
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-pencil"
@click="openEditTab(config.selectedTabId.value)">Rename</UButton>
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-arrow-up"
@click="moveTab(config.selectedTabId.value, -1)" />
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-arrow-down"
@click="moveTab(config.selectedTabId.value, 1)" />
              <UButton
size="xs"
color="error"
variant="ghost"
icon="i-lucide-trash-2"
@click="removeTab(config.selectedTabId.value)" />
            </div>
            <UButton
size="sm"
icon="i-lucide-plus"
color="primary"
variant="soft"
@click="openCreateColumn">Add column</UButton>
          </div>

          <UTable :data="visibleColumns" :columns="columnTableColumns">
            <template #order-cell="{ row }">
              <span class="text-xs tabular-nums text-muted">{{ row.index + 1 }}</span>
            </template>
            <template #label-cell="{ row }">
              <div class="flex flex-col">
                <span class="text-sm font-medium text-highlighted">{{ row.original.label }}</span>
                <span class="text-[11px] text-muted">{{ row.original.fieldKey }}</span>
              </div>
            </template>
            <template #fieldType-cell="{ row }">
              <UBadge color="neutral" variant="subtle" size="sm">{{ String(row.original.fieldType).replace('_', ' ') }}</UBadge>
            </template>
            <template #referenceType-cell="{ row }">
              <span class="text-xs text-muted">{{ row.original.referenceType || 'â€”' }}</span>
            </template>
            <template #isRequired-cell="{ row }">
              <UIcon :name="row.original.isRequired ? 'i-lucide-check' : 'i-lucide-minus'" :class="row.original.isRequired ? 'text-primary' : 'text-muted'" />
            </template>
            <template #isActive-cell="{ row }">
              <USwitch :model-value="Boolean(row.original.isActive)" :disabled="Boolean(row.original.isArchived)" @update:model-value="toggleColumn(String(row.original.id), Boolean($event))" />
            </template>
            <template #actions-cell="{ row }">
              <div class="flex items-center justify-end gap-1">
                <UBadge
v-if="row.original.isArchived"
color="warning"
variant="subtle"
size="sm">archived</UBadge>
                <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-pencil"
@click="openEditColumn(String(row.original.id))" />
                <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-arrow-up"
@click="moveColumn(String(row.original.id), -1)" />
                <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-arrow-down"
@click="moveColumn(String(row.original.id), 1)" />
                <UButton
size="xs"
color="error"
variant="ghost"
icon="i-lucide-trash-2"
@click="removeColumn(String(row.original.id))" />
              </div>
            </template>
          </UTable>
        </template>
        <UEmpty
          v-else
          variant="naked"
          icon="i-lucide-columns-3"
          title="No tab selected"
          description="Create a tab to configure its dynamic table columns."
          class="py-16" />
      </section>
    </div>

    <UModal v-model:open="tabModalOpen" :title="tabForm.id ? 'Edit tab' : 'Add tab'">
      <template #body>
        <div class="space-y-3">
          <UFormField label="Name" required>
            <UInput v-model="tabForm.name" placeholder="Inspection" class="w-full" />
          </UFormField>
          <UFormField label="Code" help="URL slug used in ?section=. Leave blank to derive from the name.">
            <UInput
v-model="tabForm.code"
placeholder="inspection"
class="w-full"
:disabled="Boolean(tabForm.id)" />
          </UFormField>
          <UFormField label="Icon">
            <UInput v-model="tabForm.icon" placeholder="i-lucide-table" class="w-full" />
          </UFormField>
          <div class="flex items-center gap-4">
            <UFormField label="Order">
              <UInput v-model="tabForm.sortOrder" type="number" class="w-24" />
            </UFormField>
            <UCheckbox v-model="tabForm.isActive" label="Active" />
            <UCheckbox v-model="tabForm.allowMultipleRows" label="Allow multiple rows" />
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="ghost" @click="tabModalOpen = false">Cancel</UButton>
          <UButton color="primary" @click="saveTab">Save</UButton>
        </div>
      </template>
    </UModal>

    <UModal v-model:open="columnModalOpen" :title="columnForm.id ? 'Edit column' : 'Add column'">
      <template #body>
        <div class="space-y-3">
          <UFormField label="Label" required>
            <UInput v-model="columnForm.label" placeholder="Invoice No." class="w-full" />
          </UFormField>
          <UFormField label="Field key" help="Stored key in each row's JSON values.">
            <UInput
v-model="columnForm.fieldKey"
class="w-full"
:disabled="Boolean(columnForm.id)"
@update:model-value="columnForm.keyTouched = true" />
          </UFormField>
          <div class="grid grid-cols-2 gap-3">
            <UFormField label="Type">
              <USelect v-model="columnForm.fieldType" :items="typeItems" class="w-full" />
            </UFormField>
            <UFormField v-if="columnForm.fieldType === 'reference'" label="Reference type">
              <USelect v-model="columnForm.referenceType" :items="referenceItems" class="w-full" />
            </UFormField>
            <UFormField v-else label="Width" help="Optional CSS width, e.g. 160px.">
              <UInput v-model="columnForm.width" class="w-full" />
            </UFormField>
          </div>
          <UFormField v-if="needsOptions" label="Options" help="One option per line.">
            <UTextarea
v-model="columnForm.optionsText"
:rows="5"
class="w-full"
placeholder="Pending&#10;Approved&#10;Paid" />
          </UFormField>
          <div class="flex flex-wrap items-center gap-4">
            <UCheckbox v-model="columnForm.isRequired" label="Required" />
            <UCheckbox v-model="columnForm.isActive" label="Active" />
            <UCheckbox v-model="columnForm.showInSummary" label="Show in summary" />
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="ghost" @click="columnModalOpen = false">Cancel</UButton>
          <UButton color="primary" @click="saveColumn">Save</UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
