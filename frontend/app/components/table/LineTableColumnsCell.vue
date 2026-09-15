<script setup lang="ts">
import type { DynamicTableColumnDef } from '~/types/docetra/configuration'
import { parseDynamicTableColumns } from '~/utils/freight/dynamic-table'

const props = defineProps<{
  modelValue: unknown
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [DynamicTableColumnDef[]]
}>()

const { t } = useI18n()
const open = ref(false)

const columns = computed<DynamicTableColumnDef[]>({
  get: () => parseDynamicTableColumns(props.modelValue),
  set: (value) => {
    emit('update:modelValue', value)
  },
})

function close() {
  open.value = false
}
</script>

<template>
  <div>
    <UButton
      color="neutral"
      variant="outline"
      size="xs"
      icon="i-lucide-columns-3"
      :label="t('docetra.config.editTableColumns', { count: columns.length })"
      :disabled="disabled"
      @click="open = true"
    />

    <UModal
      v-model:open="open"
      :title="t('docetra.config.tableColumnsTitle')"
      :ui="{ content: 'w-[calc(100%-2rem)] max-w-3xl sm:max-w-3xl' }"
      @update:open="value => !value && close()"
    >
      <template #body>
        <ConfigurationAppTableColumnsBuilder v-model="columns" />
      </template>
      <template #footer>
        <div class="flex justify-end">
          <UButton
            color="primary"
            size="sm"
            :label="t('actions.close')"
            @click="close"
          />
        </div>
      </template>
    </UModal>
  </div>
</template>
