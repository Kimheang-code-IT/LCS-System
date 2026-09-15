<script setup lang="ts">
import type { ConfigWorkflowStage, WorkflowTransition } from '~/types/docetra/configuration'
import { createClientId } from '~/utils/client-id'

const stages = defineModel<ConfigWorkflowStage[]>('stages', { default: () => [] })
const transitions = defineModel<WorkflowTransition[]>('transitions', { default: () => [] })

const { t } = useI18n()

function addStage() {
  const order = stages.value.length
  stages.value = [
    ...stages.value,
    {
      id: createClientId('st'),
      name: `Stage ${order + 1}`,
      code: `stage_${order + 1}`,
      color: '#64748b',
      isInitial: order === 0,
      isFinal: false,
      order,
    },
  ]
}

function updateStage(id: string, patch: Partial<ConfigWorkflowStage>) {
  let next = stages.value.map(s => (s.id === id ? { ...s, ...patch } : s))
  if (patch.isInitial) {
    next = next.map(s => ({ ...s, isInitial: s.id === id }))
  }
  stages.value = next
}

function removeStage(id: string) {
  const removed = stages.value.find(s => s.id === id)
  stages.value = stages.value
    .filter(s => s.id !== id)
    .map((s, index) => ({ ...s, order: index }))
  if (removed) {
    transitions.value = transitions.value.filter(
      tr => tr.fromStageCode !== removed.code && tr.toStageCode !== removed.code,
    )
  }
}

function onReorder(items: ConfigWorkflowStage[]) {
  stages.value = items.map((s, index) => ({ ...s, order: index }))
}

function addTransition() {
  const codes = stages.value.map(s => s.code)
  if (codes.length < 2) return
  transitions.value = [
    ...transitions.value,
    {
      id: createClientId('tr'),
      fromStageCode: codes[0]!,
      toStageCode: codes[1]!,
    },
  ]
}

function updateTransition(id: string, patch: Partial<WorkflowTransition>) {
  transitions.value = transitions.value.map(tr =>
    tr.id === id ? { ...tr, ...patch } : tr,
  )
}

function removeTransition(id: string) {
  transitions.value = transitions.value.filter(tr => tr.id !== id)
}

const stageItems = computed(() =>
  stages.value.map(s => ({ label: `${s.name} (${s.code})`, value: s.code })),
)
</script>

<template>
  <div class="space-y-6">
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h4 class="text-sm font-semibold">
          {{ t('docetra.config.stages') }}
        </h4>
        <UButton icon="i-lucide-plus" size="sm" @click="addStage">
          {{ t('docetra.config.addStage') }}
        </UButton>
      </div>

      <CommonAppSortableList :items="stages" @reorder="onReorder">
        <template #default="{ item }">
          <div class="grid gap-2 sm:grid-cols-12 sm:items-center">
            <UInput
              :model-value="item.name"
              class="sm:col-span-3"
              size="sm"
              @update:model-value="updateStage(item.id, { name: String($event) })"
            />
            <UInput
              :model-value="item.code"
              class="sm:col-span-2"
              size="sm"
              @update:model-value="updateStage(item.id, { code: String($event) })"
            />
            <UInput
              :model-value="item.color || ''"
              class="sm:col-span-2"
              size="sm"
              placeholder="#2563eb"
              @update:model-value="updateStage(item.id, { color: String($event) })"
            />
            <UCheckbox
              class="sm:col-span-2"
              :model-value="item.isInitial"
              :label="t('docetra.config.initial')"
              @update:model-value="updateStage(item.id, { isInitial: Boolean($event) })"
            />
            <UCheckbox
              class="sm:col-span-2"
              :model-value="item.isFinal"
              :label="t('docetra.config.final')"
              @update:model-value="updateStage(item.id, { isFinal: Boolean($event) })"
            />
            <UButton
              class="sm:col-span-1"
              icon="i-lucide-trash-2"
              color="error"
              variant="ghost"
              size="xs"
              @click="removeStage(item.id)"
            />
          </div>
        </template>
        <template #empty>
          {{ t('docetra.config.noStages') }}
        </template>
      </CommonAppSortableList>
    </div>

    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <h4 class="text-sm font-semibold">
          {{ t('docetra.config.transitions') }}
        </h4>
        <UButton
          icon="i-lucide-plus"
          size="sm"
          :disabled="stages.length < 2"
          @click="addTransition"
        >
          {{ t('docetra.config.addTransition') }}
        </UButton>
      </div>

      <div
        v-for="tr in transitions"
        :key="tr.id"
        class="flex flex-wrap items-center gap-2 rounded-lg border border-default p-2"
      >
        <USelect
          :model-value="tr.fromStageCode"
          :items="stageItems"
          value-key="value"
          label-key="label"
          class="min-w-40"
          size="sm"
          @update:model-value="updateTransition(tr.id, { fromStageCode: String($event) })"
        />
        <UIcon name="i-lucide-arrow-right" class="size-4 text-muted" />
        <USelect
          :model-value="tr.toStageCode"
          :items="stageItems"
          value-key="value"
          label-key="label"
          class="min-w-40"
          size="sm"
          @update:model-value="updateTransition(tr.id, { toStageCode: String($event) })"
        />
        <UButton
          icon="i-lucide-trash-2"
          color="error"
          variant="ghost"
          size="xs"
          @click="removeTransition(tr.id)"
        />
      </div>
      <p v-if="!transitions.length" class="text-sm text-muted">
        {{ t('docetra.config.noTransitions') }}
      </p>
    </div>
  </div>
</template>
