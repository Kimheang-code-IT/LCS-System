<script setup lang="ts">
import type { PrintSettlement } from '~/utils/freight/print-model'

const props = defineProps<{ settlement: PrintSettlement, title?: string, variant?: 'default' | 'tax-invoice' }>()

const rows = computed(() => {
  const items = [
    { label: 'freight.print.fields.accountName', value: props.settlement.accountName },
    { label: 'freight.print.fields.accountNo', value: props.settlement.accountNumber },
    { label: 'freight.print.fields.bankName', value: props.settlement.bankName },
    { label: 'freight.print.fields.swiftCode', value: props.settlement.swiftCode },
  ]
  if (props.variant !== 'tax-invoice') {
    items.splice(1, 0,
      { label: 'freight.print.fields.accountAddress', value: props.settlement.accountAddress },
    )
    items.push({ label: 'freight.print.fields.branchName', value: props.settlement.branchName })
  }
  return items.filter(item => item.value)
})
</script>

<template>
  <div class="bank-block" :class="variant === 'tax-invoice' ? 'bank-block--tax' : ''">
    <p v-if="title" class="bank-block__title">{{ title }}</p>
    <div v-for="row in rows" :key="row.label" class="bank-block__row">
      <span class="bank-block__label">{{ $t(row.label) }}</span>
      <span class="bank-block__value">{{ row.value }}</span>
    </div>
  </div>
</template>

<style scoped>
.bank-block {
  font-size: 10px;
  line-height: 1.45;
  color: #000;
}

.bank-block__title {
  margin: 0 0 4px;
  font-weight: 600;
}

.bank-block__row + .bank-block__row {
  margin-top: 2px;
}

.bank-block--tax .bank-block__row {
  display: block;
}

.bank-block--tax .bank-block__row + .bank-block__row {
  margin-top: 4px;
}

.bank-block--tax .bank-block__label::after {
  content: ': ';
}

.bank-block:not(.bank-block--tax) .bank-block__row {
  display: grid;
  grid-template-columns: 30mm 1fr;
  gap: 0 2mm;
}

.bank-block:not(.bank-block--tax) .bank-block__label {
  color: #4b5563;
}
</style>
