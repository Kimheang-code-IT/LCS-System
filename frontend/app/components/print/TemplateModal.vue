<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import { defaultPrintTemplate, supportedPrintTemplates, type PrintTemplateId } from '~/config/print-templates'
import { useLcs } from '~/composables/freight/useLcs'
import { financialContainerOptions, type FinancialPrintData } from '~/utils/freight/financial-print'
import { apiErrorMessage } from '~/utils/validation/api-error'

const props = defineProps<{
  open: boolean
  collection: string
  record?: FreightRecord | null
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'print', templateId: PrintTemplateId, containerId?: string): void
}>()

const { t } = useI18n()

const selected = ref<PrintTemplateId>('tax-invoice')
const lcs = useLcs()
const financial = computed(() => props.collection === 'debitNotes' && props.record?.documentType === 'CUSTOMER_INVOICE')
const printData = ref<FinancialPrintData | null>(null)
const selectedContainer = ref('')
const loading = ref(false)
const errorMessage = ref('')
let loadVersion = 0
const containerOptions = computed(() => financialContainerOptions(printData.value))
const canPrint = computed(() => !loading.value && !errorMessage.value && (!financial.value
  || (printData.value && !printData.value.warnings.length && (selected.value !== 'debit-note' || containerOptions.value.some(row => row.value === selectedContainer.value)))))

watch(
  () => [props.open, props.collection, props.record?.id] as const,
  async () => {
    const version = ++loadVersion
    errorMessage.value = ''
    printData.value = null
    selectedContainer.value = ''
    if (!props.open) return
    selected.value = defaultPrintTemplate(props.collection, props.record)
    if (!financial.value) return
    loading.value = true
    try {
      const data = await lcs.finance.getPrintData(String(props.record?.id), 'tax-invoice')
      if (version !== loadVersion) return
      printData.value = data
      if (data.containers.length === 1) selectedContainer.value = data.containers[0]!.id
    }
    catch (error) {
      if (version === loadVersion) errorMessage.value = apiErrorMessage(error, t('api.requestFailed'))
    }
    finally {
      if (version === loadVersion) loading.value = false
    }
  },
  { immediate: true },
)

const templates = computed(() => supportedPrintTemplates(props.collection))

function close() {
  emit('update:open', false)
}

function printSelected() {
  if (!canPrint.value) return
  emit('print', selected.value, financial.value && selected.value === 'debit-note' ? selectedContainer.value : undefined)
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
          <span class="mb-1 block text-sm font-medium text-highlighted">{{ t(financial && template.id === 'tax-invoice' && printData && !printData.taxInvoiceEligible ? 'freight.print.title.invoice' : template.labelKey) }}</span>
          <span class="block text-xs text-muted">{{ t(template.descriptionKey) }}</span>
          <span class="mt-2 inline-block text-[11px] text-dimmed">
            {{ template.orientation === 'landscape' ? t('freight.print.a4Landscape') : t('freight.print.a4Portrait') }}
          </span>
        </button>
      </div>
      <p v-if="financial" class="mt-3 text-xs text-muted">{{ t('freight.print.savedScope') }}</p>
      <UFormField
        v-if="financial && selected === 'debit-note'"
        class="mt-3"
        :label="t('freight.print.actualContainer')"
        data-field-key="containerId"
      >
        <USelectMenu
          v-model="selectedContainer"
          :items="containerOptions"
          value-key="value"
          class="w-full"
          :loading="loading"
          :aria-label="t('freight.print.actualContainer')"
        />
        <p v-if="!loading && !containerOptions.length" class="mt-1 text-sm text-error">{{ t('freight.print.noContainers') }}</p>
      </UFormField>
      <p v-if="errorMessage" role="alert" class="mt-3 text-sm text-error">{{ errorMessage }}</p>
      <p v-if="printData?.warnings.length" role="alert" class="mt-3 text-sm text-error">{{ printData.warnings.join(' ') }}</p>
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
          :disabled="!canPrint"
          :loading="loading"
          @click="printSelected"
        />
      </div>
    </template>
  </UModal>
</template>
