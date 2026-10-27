<script setup lang="ts">
import type {
  ComponentDataCardinality,
  ComponentDisplayMode,
  ComponentFormColumns,
  ComponentGroupLayoutInput,
  ComponentTab,
  ComponentTabGroupLink,
} from '~/types/component-config'
import {
  COMPONENT_DATA_CARDINALITY_VALUES,
  COMPONENT_DISPLAY_MODE_VALUES,
  COMPONENT_FORM_COLUMN_VALUES,
  resolveComponentLayout,
} from '~/utils/freight/component-layout'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateDraftFields } from '~/utils/validation/record-validation'
import { apiErrorMessage } from '~/utils/validation/api-error'

definePageMeta({
  titleKey: 'freight.pages.componentTabs',
  permission: 'configuration.manage',
})

type TabDraft = { id?: string, name: string, description: string, directionId: string }

/** Required inputs of the create/rename dialog, shared with the validator. */
const TAB_DRAFT_FIELDS = [
  { key: 'name', label: 'Name', required: true },
] as const

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()
const store = useFreightStore()

const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: key => TAB_DRAFT_FIELDS.find(field => field.key === key)?.label || key,
  order: () => TAB_DRAFT_FIELDS.map(field => field.key),
})
const pageErrors = ref<string[]>([])

const selectedTabId = ref('')
const addGroupId = ref<string | undefined>(undefined)
const draft = ref<TabDraft>({ name: '', description: '', directionId: '' })
const dialogOpen = ref(false)

type LayoutDraft = {
  displayMode: ComponentDisplayMode
  dataCardinality: ComponentDataCardinality
  formColumns: ComponentFormColumns
  showGroupTitle: boolean
  editable: boolean
  collapsible: boolean
  defaultExpanded: boolean
}

const layoutDialogOpen = ref(false)
const layoutTarget = ref<ComponentTabGroupLink | null>(null)
const layoutDraft = ref<LayoutDraft>({
  displayMode: 'form_only',
  dataCardinality: 'single',
  formColumns: 2,
  showGroupTitle: true,
  editable: true,
  collapsible: false,
  defaultExpanded: true,
})

const displayModeOptions = computed(() => COMPONENT_DISPLAY_MODE_VALUES.map(value => ({
  label: t(`freight.componentLayout.modes.${value}`),
  value,
})))
const cardinalityOptions = computed(() => COMPONENT_DATA_CARDINALITY_VALUES.map(value => ({
  label: t(`freight.componentLayout.cardinalities.${value}`),
  value,
})))
const columnOptions = COMPONENT_FORM_COLUMN_VALUES.map(value => ({ label: `${value}`, value }))

function layoutValueFor(link: ComponentTabGroupLink): LayoutDraft {
  const layout = resolveComponentLayout(link)
  return {
    displayMode: layout.displayMode,
    dataCardinality: layout.dataCardinality,
    formColumns: layout.formColumns,
    showGroupTitle: layout.showGroupTitle,
    editable: layout.editable,
    collapsible: layout.collapsible,
    defaultExpanded: layout.defaultExpanded,
  }
}

function openLayout(link: ComponentTabGroupLink) {
  layoutTarget.value = link
  layoutDraft.value = layoutValueFor(link)
  pageErrors.value = []
  layoutDialogOpen.value = true
}

/** A form-only group has no table, so multiple records is not a legal pairing. */
watch(() => layoutDraft.value.displayMode, (mode) => {
  if (mode === 'form_only') layoutDraft.value.dataCardinality = 'single'
})

async function saveLayout() {
  const target = layoutTarget.value
  if (!target) return
  const input: ComponentGroupLayoutInput = { ...layoutDraft.value }
  try {
    await config.updateTabGroup(target.tabGroupId, input)
    layoutDialogOpen.value = false
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

async function moveGroup(index: number, direction: -1 | 1) {
  const links = [...config.tabGroups.value]
  const target = index + direction
  if (target < 0 || target >= links.length || !selectedTabId.value) return
  const [moved] = links.splice(index, 1)
  links.splice(target, 0, moved!)
  try {
    await config.reorderTabGroups(selectedTabId.value, links.map(link => link.tabGroupId))
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
  }
}

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
  validation.reset()
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
  const failures = validateDraftFields(
    current as unknown as Record<string, unknown>,
    TAB_DRAFT_FIELDS.map(field => ({ key: field.key, required: field.required })),
    key => TAB_DRAFT_FIELDS.find(field => field.key === key)?.label || key,
  )
  if (failures.length) {
    validation.applyFailures(failures)
    void validation.focusFirstInvalid()
    return
  }
  validation.reset()
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
  catch (error) {
    validation.applyServerError(error)
    void validation.focusFirstInvalid()
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
    const link = config.tabGroups.value.find(item => item.id === groupId)
    if (link) openLayout(link)
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    pageErrors.value = [apiErrorMessage(error, t('freight.ui.saveFailed'))]
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
  <div class="mx-auto flex w-[95%] max-w-[1800px] flex-col gap-4 p-4">
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
                <th class="px-3 py-2 font-medium">Layout</th>
                <th class="px-3 py-2 font-medium">Records</th>
                <th class="px-3 py-2 font-medium">Columns</th>
                <th class="w-24" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(link, index) in config.tabGroups.value"
                :key="link.tabGroupId"
                class="border-t border-default"
              >
                <td class="px-3 py-2 text-highlighted">
                  <div class="flex flex-col">
                    <span class="font-medium">{{ link.name }}</span>
                    <span class="text-[11px] text-muted">{{ link.code }}</span>
                  </div>
                </td>
                <td class="px-3 py-2">
                  <UBadge color="neutral" variant="subtle" size="sm">
                    {{ t(`freight.componentLayout.modes.${resolveComponentLayout(link).displayMode}`) }}
                  </UBadge>
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ t(`freight.componentLayout.cardinalities.${resolveComponentLayout(link).dataCardinality}`) }}
                </td>
                <td class="px-3 py-2 text-muted">
                  {{ resolveComponentLayout(link).formColumns }}
                </td>
                <td class="px-1 py-1 text-right">
                  <div class="flex items-center justify-end">
                    <UButton
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-arrow-up"
                      :disabled="index === 0"
                      :aria-label="t('actions.moveUp')"
                      @click="moveGroup(index, -1)"
                    />
                    <UButton
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-arrow-down"
                      :disabled="index === config.tabGroups.value.length - 1"
                      :aria-label="t('actions.moveDown')"
                      @click="moveGroup(index, 1)"
                    />
                    <UButton
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-sliders-horizontal"
                      :aria-label="t('freight.componentLayout.editLayout')"
                      @click="openLayout(link)"
                    />
                    <UButton
                      size="xs"
                      color="error"
                      variant="ghost"
                      icon="i-lucide-trash-2"
                      :aria-label="t('actions.delete')"
                      @click="removeMembership(link)"
                    />
                  </div>
                </td>
              </tr>
              <tr class="border-t border-default">
                <td colspan="5" class="px-3 py-2">
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

    <CommonAppFormErrorSummary class="mb-2" :form-errors="pageErrors" />

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      :title="draft.id ? 'Rename tab' : 'Add tab'"
      :saving="config.saving.value"
      :confirm-label="draft.id ? 'Save' : 'Create'"
      :form-errors="validation.formErrors.value"
      @confirm="saveDraft"
    >
      <div class="space-y-4">
        <UFormField
          label="Name"
          required
          :error="validation.fieldErrors.value.name"
          data-field-key="name"
        >
          <UInput
            v-model="draft.name"
            placeholder="Tab name"
            class="w-full"
            @update:model-value="validation.clearFieldError('name')"
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

    <CommonAppEntityDialog
      v-model:open="layoutDialogOpen"
      :title="t('freight.componentLayout.editLayout')"
      :saving="config.saving.value"
      :confirm-label="t('actions.save')"
      :form-errors="[]"
      @confirm="saveLayout"
    >
      <div class="space-y-4">
        <p v-if="layoutTarget" class="text-sm text-muted">
          {{ t('freight.componentLayout.groupHint', { name: layoutTarget.name, tab: selectedTab?.name || '' }) }}
        </p>

        <UFormField :label="t('freight.componentLayout.displayMode')" required>
          <USelect
            v-model="layoutDraft.displayMode"
            :items="displayModeOptions"
            class="w-full" />
        </UFormField>
        <p class="-mt-2 text-xs text-muted">
          {{ t(`freight.componentLayout.modeHints.${layoutDraft.displayMode}`) }}
        </p>

        <UFormField :label="t('freight.componentLayout.dataCardinality')" required>
          <USelect
            v-model="layoutDraft.dataCardinality"
            :items="cardinalityOptions"
            :disabled="layoutDraft.displayMode === 'form_only'"
            class="w-full" />
        </UFormField>

        <UFormField :label="t('freight.componentLayout.formColumns')">
          <USelect
            v-model="layoutDraft.formColumns"
            :items="columnOptions"
            class="w-full" />
        </UFormField>

        <div class="grid gap-3 sm:grid-cols-2">
          <UFormField :label="t('freight.componentLayout.showGroupTitle')">
            <USwitch v-model="layoutDraft.showGroupTitle" />
          </UFormField>
          <UFormField :label="t('freight.componentLayout.editable')">
            <USwitch v-model="layoutDraft.editable" />
          </UFormField>
          <UFormField :label="t('freight.componentLayout.collapsible')">
            <USwitch v-model="layoutDraft.collapsible" />
          </UFormField>
          <UFormField :label="t('freight.componentLayout.defaultExpanded')">
            <USwitch v-model="layoutDraft.defaultExpanded" :disabled="!layoutDraft.collapsible" />
          </UFormField>
        </div>
      </div>
    </CommonAppEntityDialog>
  </div>
</template>
