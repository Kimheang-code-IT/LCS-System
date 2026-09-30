<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ComponentGroup, ComponentGroupAttribute, ComponentRenderMode } from '~/types/freight/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'

definePageMeta({
  titleKey: 'freight.pages.componentGroups',
  permission: 'configuration.manage',
})

type GroupDraft = { id?: string, name: string, renderMode: ComponentRenderMode }

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()

const selectedGroupId = ref('')
const addAttributeId = ref<string | undefined>(undefined)
const draft = ref<GroupDraft | null>(null)

const renderModeItems = [
  { label: 'Table (repeatable rows)', value: 'table' },
  { label: 'Form (single record)', value: 'form' },
]

const selectedGroup = computed(() => config.groups.value.find(group => group.id === selectedGroupId.value) || null)
const availableAttributes = computed(() => {
  const used = new Set(config.groupAttributes.value.map(item => item.attributeId))
  return config.attributes.value
    .filter(attribute => attribute.status === 'ACTIVE' && !used.has(attribute.id))
    .map(attribute => ({ label: attribute.label, value: attribute.id }))
})

const columns: TableColumn<ComponentGroupAttribute>[] = [
  { accessorKey: 'code', header: 'Attribute' },
  { accessorKey: 'dataType', header: 'Type' },
  { accessorKey: 'isRequired', header: 'Required' },
  { id: 'actions', header: '' },
]

onMounted(async () => {
  await Promise.all([config.loadGroups(true), config.loadAttributes(false)])
  if (config.groups.value.length) await selectGroup(config.groups.value[0]!.id)
})

async function selectGroup(id: string) {
  selectedGroupId.value = id
  await config.loadGroupAttributes(id)
}

function refresh() {
  void Promise.all([config.loadGroups(true), config.loadAttributes(false)])
}

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function startAdd() {
  draft.value = { name: '', renderMode: 'table' }
}

function startRename(group: ComponentGroup) {
  draft.value = { id: group.id, name: group.name, renderMode: group.renderMode }
}

function cancelDraft() {
  draft.value = null
}

async function saveDraft() {
  const current = draft.value
  if (!current || !current.name.trim()) return
  try {
    if (current.id) {
      await config.updateGroup(current.id, { name: current.name, renderMode: current.renderMode })
    }
    else {
      const created = await config.createGroup({ name: current.name, code: slugify(current.name), renderMode: current.renderMode })
      await config.loadGroups(true)
      await selectGroup(created.id)
    }
    draft.value = null
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function removeGroup(group: ComponentGroup) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.delete', descriptionParams: { name: group.name } })
  if (!accepted) return
  const result = await config.deleteGroup(group.id)
  toast.add({ title: result.archived ? t('freight.ui.archived') : t('actions.delete'), color: result.archived ? 'warning' : 'success' })
  if (selectedGroupId.value === group.id) {
    selectedGroupId.value = ''
    config.groupAttributes.value = []
  }
  await config.loadGroups(true)
}

async function changeRenderMode(value: ComponentRenderMode) {
  if (!selectedGroup.value) return
  await config.updateGroup(selectedGroup.value.id, { renderMode: value })
}

async function addAttribute() {
  if (!selectedGroupId.value || !addAttributeId.value) return
  await config.addGroupAttribute(selectedGroupId.value, { attributeId: addAttributeId.value })
  addAttributeId.value = undefined
}

function removeMembership(item: ComponentGroupAttribute) {
  if (!selectedGroupId.value) return
  void config.removeGroupAttribute(item.id)
}

async function moveMembership(index: number, direction: -1 | 1) {
  const rows = [...config.groupAttributes.value]
  const target = index + direction
  if (target < 0 || target >= rows.length) return
  const [item] = rows.splice(index, 1)
  rows.splice(target, 0, item!)
  await config.reorderGroupAttributes(selectedGroupId.value, rows.map(row => row.id))
}

function toggleRequired(item: ComponentGroupAttribute, value: boolean) {
  void config.updateGroupAttribute(item.id, { isRequired: value })
}
</script>

<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-4 p-4">
    <LayoutAppHeaderPageActions
      can-create
      create-label="Add group"
      @create="startAdd"
      @refresh="refresh"
    />

    <div class="grid gap-4 lg:grid-cols-[280px_1fr]">
      <aside class="rounded-lg border border-default bg-default p-2">
        <div class="flex items-center justify-between px-1 pb-2">
          <span class="text-xs font-semibold uppercase tracking-wide text-muted">Groups</span>
          <UBadge color="neutral" variant="subtle" size="sm">{{ config.groups.value.length }}</UBadge>
        </div>
        <div class="space-y-1">
          <div
            v-if="draft && !draft.id"
            class="flex items-center gap-1 rounded-md px-2 py-1.5 ring-1 ring-primary"
          >
            <UInput
v-model="draft.name"
placeholder="Group name"
size="xs"
class="min-w-0 flex-1"
@keyup.enter="saveDraft" />
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
          </div>

          <div
            v-for="group in config.groups.value"
            :key="group.id"
            class="flex w-full items-center rounded-md pr-0.5 transition hover:bg-elevated"
            :class="group.id === selectedGroupId ? 'bg-elevated ring-1 ring-primary' : ''"
          >
            <template v-if="draft && draft.id === group.id">
              <UInput
v-model="draft.name"
size="xs"
class="mx-2 min-w-0 flex-1"
@keyup.enter="saveDraft" />
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
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left text-sm"
                @click="selectGroup(group.id)"
              >
                <UIcon name="i-lucide-folders" class="size-4 shrink-0 text-muted" />
                <span class="flex min-w-0 flex-1 flex-col">
                  <span class="truncate font-medium text-highlighted">{{ group.name }}</span>
                  <span class="truncate text-[11px] text-muted">{{ group.renderMode }} · {{ group.attributeCount || 0 }}</span>
                </span>
              </button>
              <div class="flex shrink-0 items-center">
                <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-pencil"
aria-label="Rename"
@click="startRename(group)" />
                <UButton
size="xs"
color="error"
variant="ghost"
icon="i-lucide-trash-2"
aria-label="Delete"
@click="removeGroup(group)" />
              </div>
            </template>
          </div>
        </div>
      </aside>

      <section v-if="selectedGroup" class="rounded-lg border border-default bg-default p-3">
        <div class="flex flex-wrap items-center justify-between gap-2 pb-3">
          <h2 class="text-base font-semibold text-highlighted">{{ selectedGroup.name }}</h2>
          <USelect
            :model-value="selectedGroup.renderMode"
            :items="renderModeItems"
            class="w-56"
            @update:model-value="changeRenderMode($event as ComponentRenderMode)" />
        </div>

        <div class="flex flex-wrap items-center gap-2 pb-3">
          <USelect
v-model="addAttributeId"
:items="availableAttributes"
placeholder="Add attribute..."
class="w-64" />
          <UButton
size="sm"
color="primary"
variant="soft"
icon="i-lucide-plus"
:disabled="!addAttributeId"
@click="addAttribute">Add</UButton>
        </div>

        <UTable :data="config.groupAttributes.value" :columns="columns">
          <template #code-cell="{ row }">
            <div class="flex flex-col">
              <span class="text-sm font-medium text-highlighted">{{ row.original.label }}</span>
              <span class="text-[11px] text-muted">{{ row.original.code }}</span>
            </div>
          </template>
          <template #dataType-cell="{ row }">
            <UBadge color="neutral" variant="subtle" size="sm">{{ String(row.original.dataType).replace('_', ' ') }}</UBadge>
          </template>
          <template #isRequired-cell="{ row }">
            <USwitch :model-value="row.original.isRequired" @update:model-value="toggleRequired(row.original, Boolean($event))" />
          </template>
          <template #actions-cell="{ row }">
            <div class="flex items-center justify-end gap-1">
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-arrow-up"
aria-label="Move up"
@click="moveMembership(row.index, -1)" />
              <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-arrow-down"
aria-label="Move down"
@click="moveMembership(row.index, 1)" />
              <UButton
size="xs"
color="error"
variant="ghost"
icon="i-lucide-trash-2"
aria-label="Remove"
@click="removeMembership(row.original)" />
            </div>
          </template>
        </UTable>
      </section>
      <section v-else class="rounded-lg border border-default bg-default p-3">
        <UEmpty
variant="naked"
icon="i-lucide-folders"
title="No group selected"
description="Create a group to add attributes to it."
class="py-16" />
      </section>
    </div>
  </div>
</template>
