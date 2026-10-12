<script setup lang="ts">
import type { ComponentTab, ComponentTabGroupLink } from '~/types/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'

definePageMeta({
  titleKey: 'freight.pages.componentTabs',
  permission: 'configuration.manage',
})

type TabDraft = { id?: string, name: string, description: string, directionId: string }

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()
const store = useFreightStore()

const selectedTabId = ref('')
const addGroupId = ref<string | undefined>(undefined)
const draft = ref<TabDraft>({ name: '', description: '', directionId: '' })
const dialogOpen = ref(false)

const selectedTab = computed(() => config.tabs.value.find(tab => tab.id === selectedTabId.value) || null)
const groupOptions = computed(() => config.groups.value
  .filter(group => group.isActive && !group.isArchived)
  .filter(group => !config.tabGroups.value.some(link => link.id === group.id))
  .map(group => ({ label: group.name, value: group.id })))
const directionOptions = computed(() => store.list('tradeDirections')
  .map(row => ({ label: String(row.name || row.code || ''), value: String(row.id) })))

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
  draft.value = { name: '', description: '', directionId: '' }
  dialogOpen.value = true
}

function startRename(tab: ComponentTab) {
  draft.value = {
    id: tab.id,
    name: tab.name,
    description: tab.description || '',
    directionId: tab.tradeDirectionId ? String(tab.tradeDirectionId) : '',
  }
  dialogOpen.value = true
}

async function saveDraft() {
  const current = draft.value
  if (!current.name.trim()) return
  try {
    if (current.id) {
      await config.updateTab(current.id, {
        name: current.name,
        description: current.description,
        tradeDirectionId: current.directionId || null,
      })
    }
    else {
      const created = await config.createTab({
        name: current.name,
        code: slugify(current.name),
        description: current.description,
        tradeDirectionId: current.directionId || null,
      })
      await config.loadTabs(true)
      await selectTab(created.id)
    }
    dialogOpen.value = false
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function removeTab(tab: ComponentTab) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.deleteComponentConfirm', descriptionParams: { name: tab.name } })
  if (!accepted) return
  await config.deleteTab(tab.id)
  toast.add({ title: t('actions.delete'), color: 'success' })
  if (selectedTabId.value === tab.id) {
    selectedTabId.value = ''
    config.tabGroups.value = []
  }
  await config.loadTabs(true)
}

/** Picking a group in the trailing row assigns it to the tab right away. */
async function addGroup(groupId: string | undefined) {
  if (!selectedTabId.value || !groupId) return
  try {
    await config.addTabGroup(selectedTabId.value, groupId)
    addGroupId.value = undefined
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch {
    toast.add({ title: t('freight.ui.saveFailed'), color: 'error' })
  }
}

async function removeMembership(link: ComponentTabGroupLink) {
  if (!selectedTabId.value) return
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.deleteComponentConfirm', descriptionParams: { name: link.name } })
  if (!accepted) return
  await config.removeTabGroup(link.tabGroupId, selectedTabId.value)
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
            v-for="tab in config.tabs.value"
            :key="tab.id"
            class="flex w-full items-center rounded-md pr-0.5 transition hover:bg-elevated"
            :class="tab.id === selectedTabId ? 'bg-elevated ring-1 ring-primary' : ''"
          >
            <button
              type="button"
              class="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left text-sm"
              @click="selectTab(tab.id)"
            >
              <UIcon name="i-lucide-table" class="size-4 shrink-0 text-muted" />
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
                @click="startRename(tab)"
              />
              <UButton
                size="xs"
                color="error"
                variant="ghost"
                icon="i-lucide-trash-2"
                aria-label="Delete"
                @click="removeTab(tab)"
              />
            </div>
          </div>
        </div>
      </aside>

      <section v-if="selectedTab" class="rounded-lg border border-default bg-default p-3">
        <div class="pb-3">
          <h2 class="text-base font-semibold text-highlighted">{{ selectedTab.name }}</h2>
        </div>

        <div class="overflow-hidden rounded-md border border-default">
          <table class="w-full text-sm">
            <thead class="bg-elevated text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th class="px-3 py-2 font-medium">Group</th>
                <th class="w-10" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="link in config.tabGroups.value"
                :key="link.tabGroupId"
                class="border-t border-default"
              >
                <td class="px-3 py-2 text-highlighted">{{ link.name }}</td>
                <td class="px-1 py-1 text-right">
                  <UButton
                    size="xs"
                    color="error"
                    variant="ghost"
                    icon="i-lucide-trash-2"
                    aria-label="Remove"
                    @click="removeMembership(link)"
                  />
                </td>
              </tr>
              <tr class="border-t border-default">
                <td colspan="2" class="px-3 py-2">
                  <USelect
                    v-model="addGroupId"
                    :items="groupOptions"
                    placeholder="Add group..."
                    class="w-full max-w-sm"
                    :disabled="!groupOptions.length"
                    @update:model-value="addGroup($event as string)" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      :title="draft.id ? 'Rename tab' : 'Add tab'"
      :saving="config.saving.value"
      :confirm-label="draft.id ? 'Save' : 'Create'"
      @confirm="saveDraft"
    >
      <div class="space-y-4">
        <UFormField label="Name" required>
          <UInput
            v-model="draft.name"
            placeholder="Tab name"
            class="w-full"
            @keyup.enter="saveDraft"
          />
        </UFormField>
        <UFormField label="Trade direction">
          <USelect
            v-model="draft.directionId"
            :items="directionOptions"
            placeholder="Select trade direction..."
            class="w-full" />
        </UFormField>
        <UFormField label="Description">
          <UTextarea
            v-model="draft.description"
            placeholder="Optional description"
            :rows="3"
            autoresize
            class="w-full"
          />
        </UFormField>
      </div>
    </CommonAppEntityDialog>
  </div>
</template>
