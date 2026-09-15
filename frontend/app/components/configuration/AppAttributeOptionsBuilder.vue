<script setup lang="ts">
import type { AttributeOption } from '~/types/docetra/configuration'
import { createClientId } from '~/utils/client-id'

const model = defineModel<AttributeOption[]>({ default: () => [] })

const { t } = useI18n()

function addOption() {
  const order = model.value.length
  model.value = [
    ...model.value,
    {
      id: createClientId('opt'),
      label: `Option ${order + 1}`,
      value: `option_${order + 1}`,
      active: true,
      order,
    },
  ]
}

function updateOption(id: string, patch: Partial<AttributeOption>) {
  model.value = model.value.map(opt => (opt.id === id ? { ...opt, ...patch } : opt))
}

function removeOption(id: string) {
  model.value = model.value
    .filter(opt => opt.id !== id)
    .map((opt, index) => ({ ...opt, order: index }))
}

function onReorder(items: AttributeOption[]) {
  model.value = items.map((opt, index) => ({ ...opt, order: index }))
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm text-muted">
        {{ t('docetra.config.optionsHelp') }}
      </p>
      <UButton icon="i-lucide-plus" size="sm" @click="addOption">
        {{ t('docetra.config.addOption') }}
      </UButton>
    </div>

    <CommonAppSortableList :items="model" @reorder="onReorder">
      <template #default="{ item }">
        <div class="grid gap-2 sm:grid-cols-12 sm:items-center">
          <UInput
            :model-value="item.label"
            class="sm:col-span-3"
            size="sm"
            :placeholder="t('docetra.fields.label')"
            @update:model-value="updateOption(item.id, { label: String($event) })"
          />
          <UInput
            :model-value="item.value"
            class="sm:col-span-3"
            size="sm"
            :placeholder="t('docetra.fields.value')"
            @update:model-value="updateOption(item.id, { value: String($event) })"
          />
          <UInput
            :model-value="item.color || ''"
            class="sm:col-span-2"
            size="sm"
            placeholder="#2563eb"
            @update:model-value="updateOption(item.id, { color: String($event) })"
          />
          <UInput
            :model-value="item.icon || ''"
            class="sm:col-span-2"
            size="sm"
            placeholder="i-lucide-tag"
            @update:model-value="updateOption(item.id, { icon: String($event) })"
          />
          <div class="flex items-center justify-between gap-2 sm:col-span-2">
            <USwitch
              :model-value="item.active"
              size="sm"
              @update:model-value="updateOption(item.id, { active: Boolean($event) })"
            />
            <UButton
              icon="i-lucide-trash-2"
              color="error"
              variant="ghost"
              size="xs"
              @click="removeOption(item.id)"
            />
          </div>
        </div>
      </template>
      <template #empty>
        {{ t('docetra.config.noOptions') }}
      </template>
    </CommonAppSortableList>
  </div>
</template>
