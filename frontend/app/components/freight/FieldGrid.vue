<script setup lang="ts">
import type { FreightField } from '~/config/freight-modules'

const props = defineProps<{
  fields: FreightField[]
  model: Record<string, unknown>
  disabled?: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  update: [key: string, value: unknown]
}>()

const checkboxFields = computed(() => props.fields.filter(field => field.type === 'checkbox'))
const blockFields = computed(() => props.fields.filter(field => field.type !== 'checkbox'))
</script>

<template>
  <div
    class="grid min-w-0 grid-cols-1 sm:grid-cols-2"
    :class="compact ? 'gap-x-4 gap-y-3' : 'gap-x-5 gap-y-5'"
  >
    <div
      v-if="checkboxFields.length && blockFields[0]"
      class="flex flex-col gap-4 sm:col-span-2 sm:flex-row sm:items-end"
    >
      <FreightFieldInput
        :field="blockFields[0]"
        :model-value="model[blockFields[0].key]"
        :disabled="disabled || blockFields[0].computed"
        :compact="compact"
        class="min-w-0 flex-1"
        @update:model-value="emit('update', blockFields[0].key, $event)"
      />
      <div class="flex min-h-11 flex-wrap items-start gap-x-6 gap-y-3">
        <FreightFieldInput
          v-for="field in checkboxFields"
          :key="field.key"
          :field="field"
          :model-value="model[field.key]"
          :disabled="disabled || field.computed"
          :compact="compact"
          @update:model-value="emit('update', field.key, $event)"
        />
      </div>
    </div>
    <FreightFieldInput
      v-for="field in blockFields.slice(checkboxFields.length ? 1 : 0)"
      :key="field.key"
      :field="field"
      :model-value="model[field.key]"
      :disabled="disabled || field.computed"
      :compact="compact"
      :class="field.colSpan === 2 || field.type === 'textarea' ? 'sm:col-span-2' : ''"
      @update:model-value="emit('update', field.key, $event)"
    />
  </div>
</template>
