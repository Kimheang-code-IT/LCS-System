<script setup lang="ts">
import type { AppRolePermissionRow } from '~/types/entities'
import { useRolePermissionCatalog } from '~/composables/common/useRolePermissionCatalog'
import {
  ROLE_PERMISSION_ACTIONS,
  groupsOf,
  normalizePermissionRows,
  setPermissionAction,
} from '~/utils/role/permissions'

const rows = defineModel<AppRolePermissionRow[]>({ default: () => [] })

const props = withDefaults(defineProps<{ disabled?: boolean }>(), {
  disabled: false,
})

const { t, te } = useI18n()
const { pages: catalogPages, load: loadCatalog } = useRolePermissionCatalog()

const pageDefinitions = computed(() => catalogPages.value)
const definitions = computed(() => new Map(pageDefinitions.value.map(item => [item.value, item])))
const pageGroups = computed(() => groupsOf(pageDefinitions.value))

const search = ref('')
const baseline = ref<AppRolePermissionRow[]>([])
const expanded = ref(new Set<string>(pageGroups.value))
/** Set by the first user edit; until then the baseline follows the page catalog. */
const edited = ref(false)
const normalizedRows = computed(() => normalizePermissionRows(rows.value, true, pageDefinitions.value))
const dirty = computed(() => JSON.stringify(normalizedRows.value) !== JSON.stringify(baseline.value))

const visibleRows = computed(() => {
  const query = search.value.trim().toLocaleLowerCase()
  if (!query) return normalizedRows.value
  return normalizedRows.value.filter((row) => {
    const searchable = `${documentTypeLabel(row.documentType)} ${moduleLabel(row.documentType)} ${row.actions.join(' ')}`
      .toLocaleLowerCase()
    return searchable.includes(query)
  })
})

const groups = computed(() => pageGroups.value
  .map(key => ({
    key,
    label: te(`lcs.rolePermissions.groups.${key}`)
      ? t(`lcs.rolePermissions.groups.${key}`)
      : key,
    rows: visibleRows.value.filter(row => definitions.value.get(row.documentType)?.group === key),
  }))
  .filter(group => group.rows.length > 0))

const visibleActions = computed(() => ROLE_PERMISSION_ACTIONS.filter(action =>
  visibleRows.value.some(row => allowedActions(row.documentType).includes(action)),
))

const grantedCount = computed(() => normalizedRows.value.reduce((sum, row) => sum + row.actions.length, 0))
const totalCount = computed(() => pageDefinitions.value.reduce((sum, definition) => sum + definition.actions.length, 0))
const allGranted = computed(() => grantedCount.value === totalCount.value)
const someGranted = computed(() => grantedCount.value > 0 && !allGranted.value)
const allExpanded = computed(() => groups.value.every(group => expanded.value.has(group.key)))

function commit(next: AppRolePermissionRow[]) {
  edited.value = true
  rows.value = normalizePermissionRows(next, true, pageDefinitions.value)
}

function clone(rowsToCopy: AppRolePermissionRow[]) {
  return rowsToCopy.map(row => ({ ...row, actions: [...row.actions] }))
}

function ensureAllRows() {
  const next = normalizePermissionRows(rows.value, true, pageDefinitions.value)
  if (JSON.stringify(next) !== JSON.stringify(rows.value)) rows.value = next
  if (!baseline.value.length) rebaseline(next)
}

/**
 * Take the current rows as the "no changes yet" state.
 *
 * The page catalog arrives after mount and the parent replaces the row set when a
 * different role is opened; either one changes the shape of the matrix. Comparing
 * a new shape with an old snapshot reported unsaved changes before the user had
 * touched anything, so the baseline follows those loads until the first edit.
 */
function rebaseline(source?: AppRolePermissionRow[]) {
  baseline.value = clone(normalizePermissionRows(source ?? rows.value, true, pageDefinitions.value))
  edited.value = false
}

onMounted(() => {
  void loadCatalog()
  ensureAllRows()
  if (import.meta.client) window.addEventListener('beforeunload', warnBeforeUnload)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('beforeunload', warnBeforeUnload)
})
watch(rows, (value) => {
  ensureAllRows()
  if (!edited.value) rebaseline(value)
}, { deep: false })
watch(pageDefinitions, () => {
  if (!edited.value) rebaseline()
})

onBeforeRouteLeave(() => {
  if (!dirty.value) return true
  return import.meta.client
    ? window.confirm(t('lcs.rolePermissions.unsavedWarning'))
    : true
})

function warnBeforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

function documentTypeLabel(value: string) {
  const found = definitions.value.get(value)
  if (found && te(found.labelKey)) return t(found.labelKey)
  return value.replaceAll('_', ' ')
}

function actionLabel(action: string) {
  const key = `lcs.rolePermissions.actions.${action}`
  return te(key) ? t(key) : action.replaceAll('_', ' ')
}

function moduleLabel(documentType: string) {
  const definition = definitions.value.get(documentType)
  const moduleName = definition?.permissionPrefix.split('.')[0] || 'system'
  return moduleName.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
}

function hasAction(row: AppRolePermissionRow, action: string) {
  return row.actions.includes(action)
}

function allowedActions(documentType: string): readonly string[] {
  return definitions.value.get(documentType)?.actions || []
}

function actionAllowed(documentType: string, action: string) {
  return allowedActions(documentType).includes(action as never)
}

function toggleAction(documentType: string, action: string, checked: boolean | 'indeterminate') {
  if (props.disabled) return
  commit(normalizedRows.value.map(row =>
    row.documentType === documentType
      ? setPermissionAction(row, action, checked === true)
      : row,
  ))
}

function toggleRow(documentType: string, checked: boolean | 'indeterminate') {
  if (props.disabled) return
  commit(normalizedRows.value.map(row => row.documentType === documentType
    ? {
        ...row,
        actions: checked === true ? [...allowedActions(documentType)] : [],
        onlyIfCreator: checked === true ? row.onlyIfCreator : false,
      }
    : row))
}

/** Toggle one action for every visible row that supports it. */
function toggleActionForAll(action: string) {
  if (props.disabled) return
  const target = actionState(action) !== true
  const visible = new Set(visibleRows.value.map(row => row.documentType))
  commit(normalizedRows.value.map(row => visible.has(row.documentType) && actionAllowed(row.documentType, action)
    ? setPermissionAction(row, action, target)
    : row))
}

function actionState(action: string): boolean | 'indeterminate' {
  const supported = visibleRows.value.filter(row => actionAllowed(row.documentType, action))
  if (!supported.length) return false
  const granted = supported.filter(row => hasAction(row, action)).length
  if (granted === 0) return false
  return granted === supported.length ? true : 'indeterminate'
}

function rowState(row: AppRolePermissionRow): boolean | 'indeterminate' {
  const allowed = allowedActions(row.documentType)
  const granted = row.actions.filter(action => allowed.includes(action as never)).length
  if (granted === 0) return false
  return granted === allowed.length ? true : 'indeterminate'
}

function toggleAll(checked: boolean) {
  if (props.disabled) return
  const visible = new Set(visibleRows.value.map(row => row.documentType))
  commit(normalizedRows.value.map(row => visible.has(row.documentType)
    ? {
        ...row,
        actions: checked ? [...allowedActions(row.documentType)] : [],
        onlyIfCreator: checked ? row.onlyIfCreator : false,
      }
    : row))
}

function toggleExpanded(key: string) {
  const next = new Set(expanded.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expanded.value = next
}

function toggleAllExpanded() {
  expanded.value = allExpanded.value ? new Set() : new Set(pageGroups.value)
}

function reset() {
  if (props.disabled) return
  rows.value = clone(baseline.value)
  edited.value = false
}
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-default">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-default bg-elevated/70 px-3 py-2.5">
      <div>
        <div class="flex items-center gap-2">
          <p class="text-sm font-semibold text-highlighted">{{ $t('lcs.rolePermissions.matrixTitle') }}</p>
          <UBadge v-if="dirty" color="warning" variant="subtle">{{ $t('lcs.document.unsaved') }}</UBadge>
        </div>
        <p class="text-xs text-muted">
          {{ $t('lcs.rolePermissions.grantedCount', { granted: grantedCount, total: totalCount }) }}
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          :icon="allExpanded ? 'i-lucide-chevrons-up' : 'i-lucide-chevrons-down'"
          @click="toggleAllExpanded"
        >
          {{ allExpanded ? $t('lcs.rolePermissions.collapseAll') : $t('lcs.rolePermissions.expandAll') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-rotate-ccw"
          :disabled="disabled || !dirty"
          @click="reset"
        >
          {{ $t('lcs.rolePermissions.reset') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-shield-x"
          :disabled="disabled || grantedCount === 0"
          @click="toggleAll(false)"
        >
          {{ $t('lcs.rolePermissions.clearAll') }}
        </UButton>
        <UButton
          color="error"
          variant="soft"
          size="sm"
          icon="i-lucide-shield-plus"
          :disabled="disabled || allGranted"
          @click="toggleAll(true)"
        >
          {{ $t('lcs.rolePermissions.grantAll') }}
        </UButton>
      </div>
    </div>

    <div class="grid gap-2 border-b border-default p-3 sm:grid-cols-[minmax(0,1fr)]">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        :placeholder="$t('lcs.rolePermissions.searchPlaceholder')"
        :disabled="disabled"
      />
    </div>

    <!-- Action-wide toggles: one checkbox applies to every visible row that supports it. -->
    <div class="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-default bg-muted/20 px-3 py-2">
      <span class="text-xs font-semibold uppercase tracking-wide text-muted">
        {{ $t('lcs.rolePermissions.applyAction') }}
      </span>
      <label
        v-for="action in visibleActions"
        :key="action"
        class="flex cursor-pointer items-center gap-1.5 text-xs text-highlighted"
      >
        <UCheckbox
          :model-value="actionState(action)"
          :disabled="disabled"
          size="sm"
          :aria-label="$t('lcs.rolePermissions.toggleAction', { action: actionLabel(action) })"
          @update:model-value="toggleActionForAll(action)"
        />
        <span>{{ actionLabel(action) }}</span>
      </label>
    </div>

    <div class="overflow-x-auto">
      <table class="min-w-[58rem] w-full text-sm">
        <thead>
          <tr class="bg-elevated/50 text-left text-highlighted">
            <th class="w-12 px-3 py-2.5">
              <UCheckbox
                :model-value="allGranted ? true : someGranted ? 'indeterminate' : false"
                :disabled="disabled"
                :aria-label="$t('lcs.rolePermissions.grantAll')"
                @update:model-value="toggleAll($event === true)"
              />
            </th>
            <th class="w-[24%] whitespace-nowrap px-3 py-2.5 font-semibold">
              {{ $t('lcs.rolePermissions.documentType') }}
            </th>
            <th class="px-3 py-2.5 font-semibold">{{ $t('lcs.fields.permissions') }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="groupItem in groups" :key="groupItem.key">
            <tr class="border-t border-default bg-muted/30">
              <td colspan="3" class="px-3 py-2">
                <button
                  type="button"
                  class="flex w-full items-center gap-2 text-left text-xs font-semibold uppercase tracking-wide text-muted hover:text-highlighted"
                  @click="toggleExpanded(groupItem.key)"
                >
                  <UIcon
                    :name="expanded.has(groupItem.key) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                    class="size-4"
                  />
                  {{ groupItem.label }}
                </button>
              </td>
            </tr>
            <tr
              v-for="row in (expanded.has(groupItem.key) ? groupItem.rows : [])"
              :key="row.documentType"
              class="align-top border-t border-default"
            >
              <td class="px-3 py-3">
                <UCheckbox
                  :model-value="rowState(row)"
                  :disabled="disabled"
                  :aria-label="$t('lcs.rolePermissions.toggleRow', { entity: documentTypeLabel(row.documentType) })"
                  @update:model-value="toggleRow(row.documentType, $event)"
                />
              </td>
              <td class="px-3 py-3 font-medium text-highlighted">
                <span class="block text-[0.68rem] font-semibold uppercase tracking-wide text-muted">
                  {{ moduleLabel(row.documentType) }}
                </span>
                <span>{{ documentTypeLabel(row.documentType) }}</span>
              </td>
              <td class="px-3 py-3">
                <div class="flex flex-wrap gap-x-4 gap-y-1.5">
                  <label
                    v-for="action in allowedActions(row.documentType)"
                    :key="action"
                    class="flex cursor-pointer items-center gap-1.5 text-xs text-highlighted sm:text-sm"
                  >
                    <UCheckbox
                      :model-value="hasAction(row, action)"
                      :disabled="disabled"
                      size="sm"
                      @update:model-value="toggleAction(row.documentType, action, $event)"
                    />
                    <span>{{ actionLabel(action) }}</span>
                  </label>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="groups.length === 0">
            <td colspan="3" class="px-3 py-8 text-center text-sm text-muted">
              {{ $t('lcs.rolePermissions.noMatching') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="border-t border-default bg-muted/30 px-3 py-2 text-xs text-muted">
      {{ $t('lcs.rolePermissions.dependencyHint') }}
    </div>
  </div>
</template>
