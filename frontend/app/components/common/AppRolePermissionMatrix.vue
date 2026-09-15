<script setup lang="ts">
import type { AppRolePermissionRow } from '~/types/docetra/entities'
import {
  ROLE_DOCUMENT_TYPES,
  ROLE_PERMISSION_ACTIONS,
  normalizePermissionRows,
  setPermissionAction,
} from '~/utils/role/permissions'

const rows = defineModel<AppRolePermissionRow[]>({ default: () => [] })

const props = withDefaults(defineProps<{ disabled?: boolean }>(), {
  disabled: false,
})

const { t, te } = useI18n()

const displayRows = computed(() => normalizePermissionRows(rows.value))
const grantedCount = computed(() => displayRows.value.reduce((sum, row) => sum + row.actions.length, 0))
const totalCount = ROLE_DOCUMENT_TYPES.reduce((sum, definition) => sum + definition.actions.length, 0)
const allGranted = computed(() => grantedCount.value === totalCount)
const someGranted = computed(() => grantedCount.value > 0 && !allGranted.value)

const actionColumns = computed(() => {
  const cols: string[][] = [[], [], []]
  ROLE_PERMISSION_ACTIONS.forEach((action, index) => cols[index % 3]!.push(action))
  return cols
})

function commit(next: AppRolePermissionRow[]) {
  rows.value = normalizePermissionRows(next)
}

function ensureAllRows() {
  const next = normalizePermissionRows(rows.value)
  if (JSON.stringify(next) !== JSON.stringify(rows.value)) rows.value = next
}

onMounted(ensureAllRows)
watch(rows, ensureAllRows, { deep: false })

function documentTypeLabel(value: string) {
  const found = ROLE_DOCUMENT_TYPES.find(item => item.value === value)
  if (found && te(found.labelKey)) return t(found.labelKey)
  return value.replaceAll('_', ' ')
}

function actionLabel(action: string) {
  const key = `docetra.rolePermissions.actions.${action}`
  return te(key) ? t(key) : action
}

function hasAction(row: AppRolePermissionRow, action: string) {
  return row.actions.includes(action)
}

function allowedActions(documentType: string) {
  return ROLE_DOCUMENT_TYPES.find(item => item.value === documentType)?.actions || []
}

function actionAllowed(documentType: string, action: string) {
  return allowedActions(documentType).includes(action as any)
}

function toggleAction(documentType: string, action: string, checked: boolean | 'indeterminate') {
  if (props.disabled) return
  commit(displayRows.value.map(row =>
    row.documentType === documentType
      ? setPermissionAction(row, action, checked === true)
      : row,
  ))
}

function toggleRow(documentType: string, checked: boolean | 'indeterminate') {
  if (props.disabled) return
  commit(displayRows.value.map(row => row.documentType === documentType
    ? {
        ...row,
        actions: checked === true ? [...allowedActions(documentType)] : [],
        onlyIfCreator: checked === true ? row.onlyIfCreator : false,
      }
    : row))
}

function toggleAll(checked: boolean) {
  if (props.disabled) return
  commit(displayRows.value.map(row => ({
    ...row,
    actions: checked ? [...allowedActions(row.documentType)] : [],
    onlyIfCreator: checked ? row.onlyIfCreator : false,
  })))
}

function updateCreatorScope(documentType: string, checked: boolean | 'indeterminate') {
  if (props.disabled) return
  commit(displayRows.value.map(row => row.documentType === documentType
    ? { ...row, onlyIfCreator: row.actions.length > 0 && checked === true }
    : row))
}

function updateLevel(documentType: string, value: string | number) {
  if (props.disabled) return
  const level = Math.min(9, Math.max(0, Number(value || 0)))
  commit(displayRows.value.map(row => row.documentType === documentType
    ? { ...row, level }
    : row))
}
</script>

<template>
  <div class="overflow-hidden rounded-lg border border-default">
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-default bg-elevated/70 px-3 py-2.5">
      <div>
        <p class="text-sm font-semibold text-highlighted">{{ $t('docetra.rolePermissions.matrixTitle') }}</p>
        <p class="text-xs text-muted">
          {{ $t('docetra.rolePermissions.grantedCount', { granted: grantedCount, total: totalCount }) }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-shield-x"
          :disabled="disabled || grantedCount === 0"
          @click="toggleAll(false)"
        >
          {{ $t('docetra.rolePermissions.clearAll') }}
        </UButton>
        <UButton
          color="error"
          variant="soft"
          size="sm"
          icon="i-lucide-shield-plus"
          :disabled="disabled || allGranted"
          @click="toggleAll(true)"
        >
          {{ $t('docetra.rolePermissions.grantAll') }}
        </UButton>
      </div>
    </div>

    <div class="overflow-x-auto">
      <table class="min-w-[58rem] w-full text-sm">
        <thead>
          <tr class="bg-elevated/50 text-left text-highlighted">
            <th class="w-12 px-3 py-2.5">
              <UCheckbox
                :model-value="allGranted ? true : someGranted ? 'indeterminate' : false"
                :disabled="disabled"
                :aria-label="$t('docetra.rolePermissions.grantAll')"
                @update:model-value="toggleAll($event === true)"
              />
            </th>
            <th class="w-[22%] whitespace-nowrap px-3 py-2.5 font-semibold">
              {{ $t('docetra.rolePermissions.documentType') }}
            </th>
            <th class="px-3 py-2.5 font-semibold">{{ $t('docetra.fields.permissions') }}</th>
            <th class="w-36 px-3 py-2.5 font-semibold">{{ $t('docetra.rolePermissions.scope') }}</th>
            <th class="w-24 px-3 py-2.5 font-semibold">{{ $t('docetra.rolePermissions.level') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in displayRows" :key="row.documentType" class="align-top border-t border-default">
            <td class="px-3 py-3">
              <UCheckbox
                :model-value="row.actions.length === allowedActions(row.documentType).length"
                :disabled="disabled"
                :aria-label="$t('docetra.rolePermissions.toggleRow', { entity: documentTypeLabel(row.documentType) })"
                @update:model-value="toggleRow(row.documentType, $event)"
              />
            </td>
            <td class="px-3 py-3 font-medium text-highlighted">
              {{ documentTypeLabel(row.documentType) }}
            </td>
            <td class="px-3 py-3">
              <div class="grid grid-cols-2 gap-x-3 gap-y-1.5 sm:grid-cols-3">
                <div v-for="(col, colIndex) in actionColumns" :key="colIndex" class="space-y-1.5">
                  <label
                    v-for="action in col"
                    :key="action"
                    class="flex cursor-pointer items-center gap-1.5 text-xs text-highlighted sm:text-sm"
                  >
                    <UCheckbox
                      :model-value="hasAction(row, action)"
                      :disabled="disabled || !actionAllowed(row.documentType, action)"
                      size="sm"
                      @update:model-value="toggleAction(row.documentType, action, $event)"
                    />
                    <span>{{ actionLabel(action) }}</span>
                  </label>
                </div>
              </div>
            </td>
            <td class="px-3 py-3">
              <UCheckbox
                :model-value="Boolean(row.onlyIfCreator)"
                :disabled="disabled || row.actions.length === 0 || row.actions.includes('purge')"
                :label="$t('docetra.rolePermissions.creatorOnly')"
                @update:model-value="updateCreatorScope(row.documentType, $event)"
              />
            </td>
            <td class="px-3 py-3">
              <UInput
                :model-value="row.level || 0"
                type="number"
                :min="0"
                :max="9"
                size="sm"
                :disabled="disabled || row.actions.length === 0"
                @update:model-value="updateLevel(row.documentType, $event)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="border-t border-default bg-muted/30 px-3 py-2 text-xs text-muted">
      {{ $t('docetra.rolePermissions.dependencyHint') }}
    </div>
  </div>
</template>
