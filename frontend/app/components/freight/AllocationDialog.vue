<script setup lang="ts">
import type { FreightRecord } from '~/types/record'
import { formatMoney } from '~/composables/freight/useFreight'
import { currencyPrecision, roundMoney, sameCurrency } from '~/utils/freight/fx'

/**
 * Allocate one payment document against an unpaid invoice or bill.
 *
 * The parent owns persistence; this dialog only collects the target and amount
 * and previews the conversion, using the same arithmetic as the backend
 * (`target = amount * paymentRate / targetRate`) so the confirmed figure is the
 * one that will be applied.
 */
const props = withDefaults(defineProps<{
  open: boolean
  source: FreightRecord | null
  targets: FreightRecord[]
  saving?: boolean
  errors?: string[]
}>(), {
  saving: false,
  errors: () => [],
})

const emit = defineEmits<{
  'update:open': [boolean]
  'confirm': [{ targetId: string, amount: number }]
}>()

const { t } = useI18n()
const targetId = ref('')
const amount = ref<number | null>(null)

const target = computed(() => props.targets.find(row => String(row.id) === targetId.value) || null)

const targetItems = computed(() => props.targets.map(row => ({
  label: `${row.documentNo} · ${formatMoney(Number(row.outstanding ?? 0), String(row.currency || ''))}`,
  value: String(row.id),
})))

const preview = computed(() => {
  const source = props.source
  const targetRow = target.value
  const value = Number(amount.value)
  if (!source || !targetRow || !Number.isFinite(value) || value <= 0) return null
  const sourceRate = Number(source.exchangeRate ?? 1)
  const targetRate = Number(targetRow.exchangeRate ?? 1)
  if (!(sourceRate > 0) || !(targetRate > 0)) return null
  const same = sameCurrency(source.currency, targetRow.currency)
  const applied = same
    ? value
    : roundMoney(value * sourceRate / targetRate, currencyPrecision(targetRow.currencyPrecision))
  const paymentBase = roundMoney(value * sourceRate, currencyPrecision(source.currencyPrecision))
  const targetBase = roundMoney(applied * targetRate, currencyPrecision(targetRow.currencyPrecision))
  return {
    sameCurrency: same,
    appliedText: formatMoney(applied, String(targetRow.currency || '')),
    differenceText: formatMoney(
      roundMoney(paymentBase - targetBase, currencyPrecision(source.currencyPrecision)),
      String(source.baseCurrency || targetRow.baseCurrency || ''),
    ),
  }
})

watch(() => props.open, (open) => {
  if (!open) return
  targetId.value = ''
  amount.value = Number(props.source?.outstanding ?? 0) || null
})

function confirm() {
  const value = Number(amount.value)
  if (!targetId.value || !Number.isFinite(value) || value <= 0) return
  emit('confirm', { targetId: targetId.value, amount: value })
}
</script>

<template>
  <CommonAppEntityDialog
    :open="open"
    :title="t('freight.ui.allocate')"
    :saving="saving"
    :confirm-label="t('freight.ui.allocate')"
    :confirm-disabled="!targetId || !amount || amount <= 0"
    :form-errors="errors"
    @update:open="emit('update:open', $event)"
    @confirm="confirm">
    <div class="space-y-4">
      <p v-if="source" class="text-sm text-muted">
        {{ source.documentNo }} · {{ formatMoney(Number(source.outstanding ?? 0), String(source.currency || '')) }}
      </p>
      <UFormField :label="t('freight.ui.relatedDocument')" required>
        <USelect v-model="targetId" :items="targetItems" class="w-full" />
      </UFormField>
      <UFormField :label="t('freight.ui.cols.amount')" required>
        <UInputNumber
          v-model="amount"
          :min="0"
          :step-snapping="false"
          :increment="false"
          :decrement="false"
          class="w-full"
          :ui="{ base: 'text-right tabular-nums' }" />
      </UFormField>
      <div
        v-if="preview"
        class="space-y-1 rounded-md border border-default bg-elevated/40 px-3 py-2 text-sm">
        <div class="flex items-center justify-between gap-3">
          <span class="text-muted">{{ t('freight.ui.appliedToInvoice') }}</span>
          <span class="font-medium tabular-nums text-highlighted">{{ preview.appliedText }}</span>
        </div>
        <div v-if="!preview.sameCurrency" class="flex items-center justify-between gap-3">
          <span class="text-muted">{{ t('freight.ui.exchangeDifference') }}</span>
          <span class="tabular-nums">{{ preview.differenceText }}</span>
        </div>
      </div>
    </div>
  </CommonAppEntityDialog>
</template>
