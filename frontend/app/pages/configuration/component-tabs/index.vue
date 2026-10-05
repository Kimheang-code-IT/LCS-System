<script setup lang="ts">
import type { ComponentTab } from '~/types/component-config'
import type { SaveGridChange } from '~/types/save-grid'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import {
  componentConfigTable,
  componentTabGroupColumns,
  componentTabGroupRows,
} from '~/utils/freight/component-config-tables'

definePageMeta({
  titleKey: 'freight.pages.componentTabs',
  permission: 'configuration.manage',
})

type TabDraft = { id?: string, name: string, icon: string }

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()
const store = useFreightStore()

const selectedTabId = ref('')
const addGroupId = ref<string | undefined>(undefined)
const draft = ref<TabDraft | null>(null)

const selectedTab = computed(() => config.tabs.value.find(tab => tab.id === selectedTabId.value) || null)
const groupOptions = computed(() => config.groups.value
  .filter(group => group.isActive && !group.isArchived)
  .filter(group => !config.tabGroups.value.some(link => link.id === group.id))
  .map(group => ({ label: group.name, value: group.id })))
const directionOptions = computed(() => store.list('tradeDirections')
  .map(row => ({ label: String(row.name || row.code || ''), value: String(row.id) })))
const selectedDirections = computed(() => (selectedTab.value?.tradeDirectionIds || []).map(String))

const groupRows = computed(() => componentTabGroupRows(config.tabGroups.value))

const groupTable = computed(() => componentConfigTable({
  key: 'componentTabGroups',
  title: t('freight.ui.assignedGroups'),
  titleKm: 'ក្រុមដែលបានចូលរួម',
  columns: componentTabGroupColumns(),
}))

onMounted(async () => {
  await Promise.all([config.loadTabs(true), config.loadGroups(false)])
  if (config.tabs.value.length) await selectTab(config.tabs.value[0]!.id)
})

async function selectTab(id: string) {
  selectedTabId.value = id
  await config.loadTabGroups(id)
}

function refresh() {
  void Promise.all([config.loadTabs(true), config.loadGroups(false)])
}

function slugify(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function startAdd() {
  draft.value = { name: '', icon: 'i-lucide-table' }
}

function startRename(tab: ComponentTab) {
  draft.value = { id: tab.id, name: tab.name, icon: tab.icon || 'i-lucide-table' }
}

function cancelDraft() {
  draft.value = null
}

async function saveDraft() {
  const current = draft.value
  if (!current || !current.name.trim()) return
  try {
    if (current.id) {
      await config.updateTab(current.id, { name: current.name, icon: current.icon })
    }
    else {
      const created = await config.createTab({ name: current.name, code: slugify(current.name), icon: current.icon })
      await config.loadTabs(true)
      await selectTab(created.id)
    }
    draft.value = null
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function removeTab(tab: ComponentTab) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.delete', descriptionParams: { name: tab.name } })
  if (!accepted) return
  await config.deleteTab(tab.id)
  toast.add({ title: t('actions.delete'), color: 'success' })
  if (selectedTabId.value === tab.id) {
    selectedTabId.value = ''
    config.tabGroups.value = []
  }
  await config.loadTabs(true)
}

async function addGroup() {
  if (!selectedTabId.value || !addGroupId.value) return
  await config.addTabGroup(selectedTabId.value, addGroupId.value)
  addGroupId.value = undefined
}

/** Tab groups carry no editable columns, so Save only persists removals + order. */
async function saveGroups(change: SaveGridChange) {
  const tabId = selectedTabId.value
  if (!tabId) return
  // The grid keys rows by group id, while the API removes by the link id.
  const linkByGroupId = new Map(config.tabGroups.value.map(link => [String(link.id), link]))
  try {
    for (const groupId of change.removedIds) {
      const link = linkByGroupId.get(groupId)
      if (link) await config.removeTabGroup(link.tabGroupId, tabId)
    }
    const order = change.rows
      .map(row => String(row.tabGroupId ?? ''))
      .filter(Boolean)
    if (order.length) await config.reorderTabGroups(tabId, order)
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
    await config.loadTabGroups(tabId)
  }
}

function setDirections(values: string[]) {
  if (!selectedTabId.value) return
  void config.setTabDirections(selectedTabId.value, values)
}
</script>

<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-4 p-4">
    <LayoutAppHeaderPageActions
      can-create
      create-label="Add tab"
      @create="startAdd"
      @refresh="refresh"
    />

    <div class="grid gap-4 lg:grid-cols-[280px_1fr]">
      <aside class="rounded-lg border border-default bg-default p-2">
        <div class="flex items-center justify-between px-1 pb-2">
          <span class="text-xs font-semibold uppercase tracking-wide text-muted">Tabs</span>
          <UBadge color="neutral" variant="subtle" size="sm">{{ config.tabs.value.length }}</UBadge>
        </div>
        <div class="space-y-1">
          <div
            v-if="draft && !draft.id"
            class="flex items-center gap-1 rounded-md px-2 py-1.5 ring-1 ring-primary"
          >
            <UInput
v-model="draft.name"
placeholder="Tab name"
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
            v-for="tab in config.tabs.value"
            :key="tab.id"
            class="flex w-full items-center rounded-md pr-0.5 transition hover:bg-elevated"
            :class="tab.id === selectedTabId ? 'bg-elevated ring-1 ring-primary' : ''"
          >
            <template v-if="draft && draft.id === tab.id">
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
                @click="selectTab(tab.id)"
              >
                <UIcon :name="tab.icon || 'i-lucide-table'" class="size-4 shrink-0 text-muted" />
                <span class="flex min-w-0 flex-1 flex-col">
                  <span class="truncate font-medium text-highlighted">{{ tab.name }}</span>
                  <span class="truncate text-[11px] text-muted">{{ tab.code }} · {{ tab.groupCount || 0 }} groups</span>
                </span>
              </button>
              <div class="flex shrink-0 items-center">
                <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-pencil"
aria-label="Rename"
@click="startRename(tab)" />
                <UButton
size="xs"
color="error"
variant="ghost"
icon="i-lucide-trash-2"
aria-label="Delete"
@click="removeTab(tab)" />
              </div>
            </template>
          </div>
        </div>
      </aside>

      <section v-if="selectedTab" class="rounded-lg border border-default bg-default p-3">
        <div class="flex flex-wrap items-center justify-between gap-2 pb-3">
          <h2 class="text-base font-semibold text-highlighted">{{ selectedTab.name }}</h2>
        </div>

        <div class="pb-3">
          <p class="pb-1 text-xs font-semibold uppercase tracking-wide text-muted">Trade directions</p>
          <USelect
            :model-value="selectedDirections"
            :items="directionOptions"
            multiple
            placeholder="Select trade directions..."
            class="w-full max-w-xl"
            @update:model-value="setDirections($event as string[])" />
        </div>

        <div class="flex flex-wrap items-center gap-2 pb-3">
          <USelect
v-model="addGroupId"
:items="groupOptions"
placeholder="Add group..."
class="w-64" />
          <UButton
size="sm"
color="primary"
variant="soft"
icon="i-lucide-plus"
:disabled="!addGroupId"
@click="addGroup">Add</UButton>
        </div>

        <TableAppSaveGrid
          :table="groupTable"
          :rows="groupRows"
          :saving="config.saving.value"
          @save="saveGroups" />
      </section>
      <section v-else class="rounded-lg border border-default bg-default p-3">
        <UEmpty
variant="naked"
icon="i-lucide-table"
title="No tab selected"
description="Create a tab and add component groups to it."
class="py-16" />
      </section>
    </div>
  </div>
</template>
