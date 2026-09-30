<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ComponentAttribute, ComponentDataType, ComponentReferenceType } from '~/types/freight/component-config'
import {
  COMPONENT_DATA_TYPES,
  COMPONENT_REFERENCE_TYPES,
} from '~/types/freight/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'

definePageMeta({
  titleKey: 'freight.pages.componentAttributes',
  permission: 'configuration.manage',
})

type Draft = {
  id?: string
  label: string
  code: string
  dataType: ComponentDataType
  referenceType?: ComponentReferenceType
  isRequired: boolean
  optionsText: string
}

type Row = ComponentAttribute & { _draft?: boolean, optionsText?: string }

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()

const draft = ref<Draft | null>(null)

const typeItems = COMPONENT_DATA_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
const referenceItems = COMPONENT_REFERENCE_TYPES.map(value => ({ label: value.replace(/_/g, ' '), value }))
const needsOptions = computed(() => ['select', 'multi_select', 'currency'].includes(draft.value?.dataType || ''))

const columns: TableColumn<Row>[] = [
  { accessorKey: 'label', header: 'Label' },
  { accessorKey: 'code', header: 'Code' },
  { accessorKey: 'dataType', header: 'Type' },
  { accessorKey: 'referenceType', header: 'Reference' },
  { accessorKey: 'isRequired', header: 'Required' },
  { id: 'options', header: 'Options' },
  { id: 'actions', header: '' },
]

const rows = computed<Row[]>(() => {
  const base = config.attributes.value as Row[]
  if (!draft.value) return base
  if (draft.value.id) {
    return base.map(row => (row.id === draft.value!.id
      ? { ...row, ...draft.value, _draft: true, optionsText: draft.value!.optionsText } as Row
      : row))
  }
  return [{ ...blankDraft(), _draft: true } as Row, ...base]
})

function blankDraft(): Draft {
  return { label: '', code: '', dataType: 'text', referenceType: undefined, isRequired: false, optionsText: '' }
}

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

function refresh() {
  void config.loadAttributes(true)
}

onMounted(refresh)

function startAdd() {
  draft.value = blankDraft()
}

function startEdit(attribute: ComponentAttribute) {
  draft.value = {
    id: attribute.id,
    label: attribute.label,
    code: attribute.code,
    dataType: attribute.dataType,
    referenceType: attribute.referenceType || undefined,
    isRequired: attribute.isRequired,
    optionsText: (attribute.options || []).map(option => (typeof option === 'string' ? option : option.value)).join(', '),
  }
}

function cancelDraft() {
  draft.value = null
}

async function saveDraft() {
  const current = draft.value
  if (!current || !current.label.trim()) return
  const payload = {
    label: current.label,
    code: current.code || slugify(current.label),
    dataType: current.dataType,
    referenceType: current.dataType === 'reference' ? (current.referenceType || null) : null,
    isRequired: current.isRequired,
    options: needsOptions.value
      ? current.optionsText.split(',').map(part => part.trim()).filter(Boolean)
      : [],
  }
  try {
    if (current.id) await config.updateAttribute(current.id, payload)
    else await config.createAttribute(payload)
    draft.value = null
    toast.add({ title: t('freight.ui.save'), color: 'success' })
    await config.loadAttributes(true)
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function remove(attribute: ComponentAttribute) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.delete', descriptionParams: { name: attribute.label } })
  if (!accepted) return
  const result = await config.deleteAttribute(attribute.id)
  toast.add({ title: result.archived ? t('freight.ui.archived') : t('actions.delete'), color: result.archived ? 'warning' : 'success' })
  await config.loadAttributes(true)
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

    <section class="rounded-lg border border-default bg-default p-3">
      <UTable :data="rows" :columns="columns">
        <template #label-cell="{ row }">
          <UInput
v-if="row.original._draft"
v-model="draft!.label"
placeholder="Container No."
class="w-full" />
          <span v-else class="text-sm font-medium text-highlighted">{{ row.original.label }}</span>
        </template>
        <template #code-cell="{ row }">
          <UInput
            v-if="row.original._draft"
            v-model="draft!.code"
            :placeholder="slugify(draft!.label)"
            :disabled="Boolean(draft!.id)"
            class="w-full" />
          <span v-else class="text-[11px] text-muted">{{ row.original.code }}</span>
        </template>
        <template #dataType-cell="{ row }">
          <USelect
v-if="row.original._draft"
v-model="draft!.dataType"
:items="typeItems"
class="w-full" />
          <UBadge
v-else
color="neutral"
variant="subtle"
size="sm">{{ String(row.original.dataType).replace('_', ' ') }}</UBadge>
        </template>
        <template #referenceType-cell="{ row }">
          <USelect
            v-if="row.original._draft && draft!.dataType === 'reference'"
            v-model="draft!.referenceType"
            :items="referenceItems"
            class="w-full" />
          <span v-else class="text-xs text-muted">{{ row.original.referenceType || '—' }}</span>
        </template>
        <template #isRequired-cell="{ row }">
          <UCheckbox v-if="row.original._draft" v-model="draft!.isRequired" />
          <UIcon v-else :name="row.original.isRequired ? 'i-lucide-check' : 'i-lucide-minus'" :class="row.original.isRequired ? 'text-primary' : 'text-muted'" />
        </template>
        <template #options-cell="{ row }">
          <UInput
            v-if="row.original._draft && needsOptions"
            v-model="draft!.optionsText"
            placeholder="Pending, Paid"
            class="w-full" />
          <span v-else class="text-xs text-muted">—</span>
        </template>
        <template #actions-cell="{ row }">
          <div class="flex items-center justify-end gap-1">
            <template v-if="row.original._draft">
              <UButton
size="xs"
color="primary"
icon="i-lucide-check"
aria-label="Save"
@click="saveDraft" />
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-x"
aria-label="Cancel"
@click="cancelDraft" />
            </template>
            <template v-else>
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-pencil"
aria-label="Edit"
@click="startEdit(row.original)" />
              <UButton
size="xs"
color="error"
variant="ghost"
icon="i-lucide-trash-2"
aria-label="Delete"
@click="remove(row.original)" />
            </template>
          </div>
        </template>
      </UTable>
    </section>
  </div>
</template>
