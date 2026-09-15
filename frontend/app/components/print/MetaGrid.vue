<script setup lang="ts">
export type PrintMetaItem = { label: string, value: string, strong?: boolean }

withDefaults(defineProps<{
  items: PrintMetaItem[]
  columns?: 1 | 2
  variant?: 'default' | 'tax-invoice' | 'dcn' | 'dcn-side' | 'dcn-shipment'
}>(), {
  columns: 1,
  variant: 'default',
})
</script>

<template>
  <dl
    class="print-meta-grid"
    :class="[
      `print-meta-grid--${variant}`,
      columns === 2 ? 'print-meta-grid--cols-2' : '',
    ]"
  >
    <div
      v-for="item in items"
      :key="item.label"
      class="print-meta-grid__row"
    >
      <dt class="print-meta-grid__label whitespace-pre-line">{{ item.label }}</dt>
      <dd
        class="print-meta-grid__value whitespace-pre-line"
        :class="{ 'print-meta-grid__value--strong': item.strong }"
      >
        {{ item.value || '-' }}
      </dd>
    </div>
  </dl>
</template>

<style scoped>
.print-meta-grid {
  margin: 0;
}

.print-meta-grid--default .print-meta-grid__row {
  display: grid;
  grid-template-columns: 26mm 1fr;
  align-items: baseline;
  gap: 0 2mm;
  margin-bottom: 1px;
  font-size: 11px;
  line-height: 1.35;
  color: #111827;
}

.print-meta-grid--default .print-meta-grid__label {
  color: #4b5563;
}

.print-meta-grid--default .print-meta-grid__value {
  margin: 0;
  min-width: 0;
  word-break: break-word;
}

.print-meta-grid--cols-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px 6mm;
}

.print-meta-grid--tax-invoice .print-meta-grid__row {
  display: grid;
  grid-template-columns: 44mm 1fr;
  gap: 0 5mm;
  align-items: start;
  margin-bottom: 8px;
}

.print-meta-grid--tax-invoice .print-meta-grid__row:last-child {
  margin-bottom: 0;
}

.print-meta-grid--tax-invoice .print-meta-grid__label {
  font-size: 11px;
  line-height: 1.4;
}

.print-meta-grid--tax-invoice .print-meta-grid__value {
  margin: 0;
  min-width: 0;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  word-break: break-word;
}

.print-meta-grid--dcn .print-meta-grid__row,
.print-meta-grid--dcn-side .print-meta-grid__row,
.print-meta-grid--dcn-shipment .print-meta-grid__row {
  display: grid;
  align-items: baseline;
  gap: 0 2mm;
  font-size: 10px;
  line-height: 1.35;
  color: #111827;
}

.print-meta-grid--dcn .print-meta-grid__row {
  grid-template-columns: 26mm 1fr;
}

.print-meta-grid--dcn-side {
  width: 100%;
  justify-self: end;
}

.print-meta-grid--dcn-side .print-meta-grid__row {
  grid-template-columns: 22mm 1fr;
  gap: 0 1mm;
  width: 100%;
}

.print-meta-grid--dcn-side .print-meta-grid__label {
  color: #111827;
}

.print-meta-grid--dcn-shipment .print-meta-grid__row {
  grid-template-columns: 22mm 1fr;
}

.print-meta-grid--dcn .print-meta-grid__label,
.print-meta-grid--dcn-side .print-meta-grid__label,
.print-meta-grid--dcn-shipment .print-meta-grid__label {
  color: #374151;
}

.print-meta-grid--dcn .print-meta-grid__label::after,
.print-meta-grid--dcn-side .print-meta-grid__label::after,
.print-meta-grid--dcn-shipment .print-meta-grid__label::after {
  content: ' :';
}

.print-meta-grid--dcn .print-meta-grid__value,
.print-meta-grid--dcn-side .print-meta-grid__value,
.print-meta-grid--dcn-shipment .print-meta-grid__value {
  margin: 0;
  min-width: 0;
  word-break: break-word;
}

.print-meta-grid__value--strong {
  font-weight: 700;
}
</style>
