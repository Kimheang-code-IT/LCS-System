<script setup lang="ts">
import type { FreightRecord } from '~/types/freight/record'
import { defaultPrintTemplate, supportedPrintTemplates, type PrintTemplateId } from '~/config/print-templates'

const props = defineProps<{
  open: boolean
  collection: string
  record?: FreightRecord | null
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'print', templateId: PrintTemplateId): void
}>()

const { t } = useI18n()

const selected = ref<PrintTemplateId>('tax-invoice')

watch(
  () => [props.open, props.collection, props.record?.id] as const,
  () => {
    if (props.open) selected.value = defaultPrintTemplate(props.collection, props.record)
  },
  { immediate: true },
)

const templates = computed(() => supportedPrintTemplates(props.collection))

function close() {
  emit('update:open', false)
}

function printSelected() {
  emit('print', selected.value)
  emit('update:open', false)
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('freight.print.selectTitle')"
    :ui="{ content: 'w-[calc(100%-2rem)] max-w-lg sm:max-w-lg' }"
    @update:open="value => !value && close()"
  >
    <template #body>
      <p class="mb-3 text-sm text-muted">{{ t('freight.print.selectHint') }}</p>
      <div class="grid gap-2 sm:grid-cols-2" role="radiogroup" :aria-label="t('freight.print.selectTitle')">
        <button
          v-for="template in templates"
          :key="template.id"
          type="button"
          role="radio"
          :aria-checked="selected === template.id"
          class="rounded-md border p-3 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          :class="selected === template.id
            ? 'border-primary bg-primary-50/60 dark:bg-primary-400/10'
            : 'border-default hover:bg-elevated'"
          @click="selected = template.id"
          @keydown.enter.prevent="selected = template.id"
        >
          <span class="mb-2 flex size-9 items-center justify-center rounded-md border border-default bg-default">
            <UIcon :name="template.icon" class="size-5 shrink-0 text-primary" />
          </span>
          <span class="mb-1 block text-sm font-medium text-highlighted">{{ t(template.labelKey) }}</span>
          <span class="block text-xs text-muted">{{ t(template.descriptionKey) }}</span>
          <span class="mt-2 inline-block text-[11px] text-dimmed">
            {{ template.orientation === 'landscape' ? t('freight.print.a4Landscape') : t('freight.print.a4Portrait') }}
          </span>
        </button>
      </div>
    </template>
    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          :label="t('actions.cancel')"
          @click="close"
        />
        <UButton
          color="primary"
          size="sm"
          icon="i-lucide-printer"
          :label="t('freight.print.print')"
          :disabled="!selected"
          @click="printSelected"
        />
      </div>
    </template>
  </UModal>
</template>
