<script setup lang="ts">
import type { ComponentGroup, ComponentGroupAttribute, ComponentRenderMode } from '~/types/component-config'
import { useComponentConfig } from '~/composables/freight/useComponentConfig'
import { useConfirm } from '~/composables/common/useConfirm'
import { useFormValidation } from '~/composables/common/useFormValidation'
import { validateDraftFields } from '~/utils/validation/record-validation'

definePageMeta({
  titleKey: 'freight.pages.componentGroups',
  permission: 'configuration.manage',
})

type GroupDraft = { id?: string, name: string, renderMode: ComponentRenderMode, description: string }

/** Required inputs of the create/rename dialog, shared with the validator. */
const GROUP_DRAFT_FIELDS = [
  { key: 'name', label: 'Name', required: true },
] as const

const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const config = useComponentConfig()

const validation = useFormValidation({
  t: (key, params) => t(key, params as Record<string, unknown>),
  label: key => GROUP_DRAFT_FIELDS.find(field => field.key === key)?.label || key,
  order: () => GROUP_DRAFT_FIELDS.map(field => field.key),
})

const selectedGroupId = ref('')
const addAttributeId = ref<string | undefined>(undefined)
const draft = ref<GroupDraft>({ name: '', renderMode: 'table', description: '' })
const dialogOpen = ref(false)

const selectedGroup = computed(() => config.groups.value.find(group => group.id === selectedGroupId.value) || null)

/**
 * An attribute is a global catalog entry, so the same attribute may be added to
 * many groups; only the current group's own assignments are excluded.
 */
const availableAttributes = computed(() => {
  const used = new Set(config.groupAttributes.value.map(item => item.attributeId))
  return config.attributes.value
    .filter(attribute => attribute.status === 'ACTIVE' && !used.has(attribute.id))
    .map(attribute => ({ label: attribute.label, value: attribute.id }))
})

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
  draft.value = { name: '', renderMode: 'table', description: '' }
  dialogOpen.value = true
}

function startRename(group: ComponentGroup) {
  draft.value = { id: group.id, name: group.name, renderMode: group.renderMode, description: group.description || '' }
  dialogOpen.value = true
}

async function saveDraft() {
  const current = draft.value
  const failures = validateDraftFields(
    current as unknown as Record<string, unknown>,
    GROUP_DRAFT_FIELDS.map(field => ({ key: field.key, required: field.required })),
    key => GROUP_DRAFT_FIELDS.find(field => field.key === key)?.label || key,
  )
  if (failures.length) {
    validation.applyFailures(failures)
    void validation.focusFirstInvalid()
    return
  }
  validation.reset()
  try {
    if (current.id) {
      await config.updateGroup(current.id, {
        name: current.name,
        renderMode: current.renderMode,
        description: current.description,
      })
    }
    else {
      const created = await config.createGroup({
        name: current.name,
        code: slugify(current.name),
        renderMode: current.renderMode,
        description: current.description,
      })
      await config.loadGroups(true)
      await selectGroup(created.id)
    }
    dialogOpen.value = false
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    validation.applyServerError(error)
    void validation.focusFirstInvalid()
  }
}

async function removeGroup(group: ComponentGroup) {
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.deleteComponentConfirm', descriptionParams: { name: group.name } })
  if (!accepted) return
  const result = await config.deleteGroup(group.id)
  toast.add({ title: result.archived ? t('freight.ui.archived') : t('actions.delete'), color: result.archived ? 'warning' : 'success' })
  if (selectedGroupId.value === group.id) {
    selectedGroupId.value = ''
    config.groupAttributes.value = []
  }
  await config.loadGroups(true)
}

/** Picking an attribute in the trailing row assigns it right away. */
async function addAttribute(attributeId: string | undefined) {
  if (!selectedGroupId.value || !attributeId) return
  try {
    await config.addGroupAttribute(selectedGroupId.value, { attributeId })
    addAttributeId.value = undefined
    toast.add({ title: t('freight.ui.save'), color: 'success' })
  }
  catch (error) {
    validation.applyServerError(error)
  }
}

async function removeMembership(row: ComponentGroupAttribute) {
  if (!selectedGroupId.value) return
  const accepted = await confirm({ kind: 'delete', descriptionKey: 'freight.ui.deleteComponentConfirm', descriptionParams: { name: row.label } })
  if (!accepted) return
  await config.removeGroupAttribute(row.id)
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
            v-for="group in config.groups.value"
            :key="group.id"
            class="flex w-full items-center rounded-md pr-0.5 transition hover:bg-elevated"
            :class="group.id === selectedGroupId ? 'bg-elevated ring-1 ring-primary' : ''"
          >
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
                @click="startRename(group)"
              />
              <UButton
                size="xs"
                color="error"
                variant="ghost"
                icon="i-lucide-trash-2"
                aria-label="Delete"
                @click="removeGroup(group)"
              />
            </div>
          </div>
        </div>
      </aside>

      <section v-if="selectedGroup" class="rounded-lg border border-default bg-default p-3">
        <div class="pb-3">
          <h2 class="text-base font-semibold text-highlighted">{{ selectedGroup.name }}</h2>
        </div>

        <div class="overflow-hidden rounded-md border border-default">
          <table class="w-full text-sm">
            <thead class="bg-elevated text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th class="px-3 py-2 font-medium">Attribute</th>
                <th class="w-10" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in config.groupAttributes.value"
                :key="row.id"
                class="border-t border-default"
              >
                <td class="px-3 py-2 text-highlighted">{{ row.label }}</td>
                <td class="px-1 py-1 text-right">
                  <UButton
                    size="xs"
                    color="error"
                    variant="ghost"
                    icon="i-lucide-trash-2"
                    aria-label="Remove"
                    @click="removeMembership(row)"
                  />
                </td>
              </tr>
              <tr class="border-t border-default">
                <td colspan="2" class="px-3 py-2">
                  <USelect
                    v-model="addAttributeId"
                    :items="availableAttributes"
                    placeholder="Add attribute..."
                    class="w-full max-w-sm"
                    :disabled="!availableAttributes.length"
                    @update:model-value="addAttribute($event as string)" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
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

    <CommonAppEntityDialog
      v-model:open="dialogOpen"
      :title="draft.id ? 'Rename group' : 'Add group'"
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
            placeholder="Group name"
            class="w-full"
            @update:model-value="validation.clearFieldError('name')"
            @keyup.enter="saveDraft"
          />
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
