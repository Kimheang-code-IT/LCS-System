<script setup lang="ts">
import type { VisibilityOperator, VisibilityRule } from '~/types/docetra/configuration'
import { VISIBILITY_OPERATORS } from '~/types/docetra/configuration'

const model = defineModel<VisibilityRule | null>({ default: null })

defineProps<{
  fieldOptions: Array<{ label: string, value: string }>
}>()

const { t } = useI18n()

const enabled = computed({
  get: () => Boolean(model.value),
  set: (on: boolean | 'indeterminate') => {
    if (on === true) {
      model.value = {
        fieldCode: '',
        operator: 'equals',
        value: '',
      }
    }
    else {
      model.value = null
    }
  },
})

const operatorItems = computed(() =>
  VISIBILITY_OPERATORS.map(op => ({
    label: t(`docetra.config.operator.${op}`),
    value: op,
  })),
)

const needsValue = computed(() => {
  const op = model.value?.operator
  return op !== 'is_empty' && op !== 'is_not_empty'
})

function patch(partial: Partial<VisibilityRule>) {
  if (!model.value) return
  model.value = { ...model.value, ...partial }
}
</script>

<template>
  <div class="space-y-4">
    <UCheckbox
      v-model="enabled"
      :label="t('docetra.config.enableVisibility')"
    />

    <div v-if="model" class="grid gap-3 md:grid-cols-3">
      <UFormField :label="t('docetra.config.whenField')" :help="t('docetra.config.whenFieldHelp')">
        <USelect
          :model-value="model.fieldCode || undefined"
          :items="fieldOptions.filter(option => String(option.value || '').trim())"
          value-key="value"
          label-key="label"
          class="w-full"
          @update:model-value="patch({ fieldCode: String($event || '') })"
        />
      </UFormField>

      <UFormField :label="t('docetra.config.operatorLabel')" :help="t('docetra.config.operatorHelp')">
        <USelect
          :model-value="model.operator"
          :items="operatorItems"
          value-key="value"
          label-key="label"
          class="w-full"
          @update:model-value="patch({ operator: $event as VisibilityOperator })"
        />
      </UFormField>

      <UFormField v-if="needsValue" :label="t('docetra.fields.value')" :help="t('docetra.config.visibilityValueHelp')">
        <UInput
          :model-value="model.value == null ? '' : String(model.value)"
          @update:model-value="patch({ value: String($event) })"
        />
      </UFormField>
    </div>

    <p class="text-xs text-muted">
      {{ t('docetra.config.visibilityHelp') }}
    </p>
  </div>
</template>
