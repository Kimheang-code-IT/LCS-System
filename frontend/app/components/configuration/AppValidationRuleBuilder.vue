<script setup lang="ts">
import type { AttributeDataType, ValidationRule } from '~/types/docetra/configuration'

const model = defineModel<ValidationRule>({ default: () => ({}) })

const props = defineProps<{
  dataType: AttributeDataType
}>()

const { t } = useI18n()

const isText = computed(() =>
  ['short_text', 'long_text', 'rich_text', 'email', 'phone', 'url'].includes(props.dataType),
)
const isNumber = computed(() =>
  ['integer', 'decimal', 'currency'].includes(props.dataType),
)
const isDate = computed(() =>
  ['date', 'time', 'datetime'].includes(props.dataType),
)
const isFile = computed(() =>
  ['file', 'image'].includes(props.dataType),
)

function patch(partial: Partial<ValidationRule>) {
  model.value = { ...model.value, ...partial }
}

function numStr(value: number | undefined) {
  return value == null ? '' : String(value)
}

function parseNum(value: unknown): number | undefined {
  if (value === '' || value == null) return undefined
  const n = Number(value)
  return Number.isFinite(n) ? n : undefined
}
</script>

<template>
  <div class="space-y-4">
    <p class="text-sm text-muted">
      {{ t('docetra.config.validationHelp') }}
    </p>

    <div v-if="isText" class="grid gap-4 md:grid-cols-3">
      <UFormField :label="t('docetra.config.minLength')" :help="t('docetra.config.minLengthHelp')">
        <UInput
          type="number"
          :model-value="numStr(model.minLength)"
          @update:model-value="patch({ minLength: parseNum($event) })"
        />
      </UFormField>
      <UFormField :label="t('docetra.config.maxLength')" :help="t('docetra.config.maxLengthHelp')">
        <UInput
          type="number"
          :model-value="numStr(model.maxLength)"
          @update:model-value="patch({ maxLength: parseNum($event) })"
        />
      </UFormField>
      <UFormField :label="t('docetra.config.pattern')" :help="t('docetra.config.patternHelp')">
        <UInput
          :model-value="model.pattern || ''"
          placeholder="^[A-Z].*"
          @update:model-value="patch({ pattern: String($event || '') || undefined })"
        />
      </UFormField>
    </div>

    <div v-else-if="isNumber" class="grid gap-4 md:grid-cols-3">
      <UFormField :label="t('docetra.config.min')" :help="t('docetra.config.minHelp')">
        <UInput
          type="number"
          :model-value="numStr(model.min)"
          @update:model-value="patch({ min: parseNum($event) })"
        />
      </UFormField>
      <UFormField :label="t('docetra.config.max')" :help="t('docetra.config.maxHelp')">
        <UInput
          type="number"
          :model-value="numStr(model.max)"
          @update:model-value="patch({ max: parseNum($event) })"
        />
      </UFormField>
      <UFormField v-if="dataType !== 'integer'" :label="t('docetra.config.precision')" :help="t('docetra.config.precisionHelp')">
        <UInput
          type="number"
          :model-value="numStr(model.precision)"
          @update:model-value="patch({ precision: parseNum($event) })"
        />
      </UFormField>
    </div>

    <div v-else-if="isDate" class="grid gap-4 md:grid-cols-2">
      <UFormField :label="t('docetra.config.minDate')" :help="t('docetra.config.minDateHelp')">
        <CommonAppInputDate
          :model-value="model.minDate || ''"
          @update:model-value="patch({ minDate: String($event || '') || undefined })"
        />
      </UFormField>
      <UFormField :label="t('docetra.config.maxDate')" :help="t('docetra.config.maxDateHelp')">
        <CommonAppInputDate
          :model-value="model.maxDate || ''"
          @update:model-value="patch({ maxDate: String($event || '') || undefined })"
        />
      </UFormField>
      <UCheckbox
        :model-value="model.allowPastDate !== false"
        :label="t('docetra.config.allowPastDate')"
        @update:model-value="patch({ allowPastDate: Boolean($event) })"
      />
      <UCheckbox
        :model-value="model.allowFutureDate !== false"
        :label="t('docetra.config.allowFutureDate')"
        @update:model-value="patch({ allowFutureDate: Boolean($event) })"
      />
    </div>

    <div v-else-if="isFile" class="grid gap-4 md:grid-cols-2">
      <UFormField :label="t('docetra.config.maxFileSizeMb')" :help="t('docetra.config.maxFileSizeHelp')">
        <UInput
          type="number"
          :model-value="numStr(model.maxFileSizeMb)"
          @update:model-value="patch({ maxFileSizeMb: parseNum($event) })"
        />
      </UFormField>
      <UFormField :label="t('docetra.config.allowedExtensions')" :help="t('docetra.config.extensionsHelp')">
        <UInput
          :model-value="(model.allowedExtensions || []).join(', ')"
          placeholder="pdf, docx, png"
          @update:model-value="patch({
            allowedExtensions: String($event || '')
              .split(',')
              .map(s => s.trim())
              .filter(Boolean),
          })"
        />
      </UFormField>
      <UCheckbox
        :model-value="Boolean(model.allowMultiple)"
        :label="t('docetra.config.allowMultiple')"
        @update:model-value="patch({ allowMultiple: Boolean($event) })"
      />
    </div>

    <UAlert
      v-else
      color="neutral"
      variant="subtle"
      :title="t('docetra.config.noValidationForType')"
      :description="t('docetra.config.noValidationForTypeHelp')"
    />
  </div>
</template>
