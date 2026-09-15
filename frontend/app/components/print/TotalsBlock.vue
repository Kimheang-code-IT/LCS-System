<script setup lang="ts">
defineProps<{
  items: Array<{
    label: string
    value: string
    strong?: boolean
    topRule?: boolean
    bottomRule?: boolean
    footer?: boolean
  }>
}>()
</script>

<template>
  <div class="totals-block">
    <div
      v-for="item in items"
      :key="item.label"
      class="totals-block__row"
      :class="{
        'totals-block__row--strong': item.strong,
        'totals-block__row--top': item.topRule,
        'totals-block__row--bottom': item.bottomRule,
        'totals-block__row--footer': item.footer,
      }"
    >
      <span class="totals-block__label font-khmer">{{ item.label }}</span>
      <span class="totals-block__value">{{ item.value }}</span>
    </div>
  </div>
</template>

<style scoped>
.totals-block {
  width: 82mm;
  font-size: 10px;
  line-height: 1.4;
  color: #000;
}

.font-khmer {
  font-family: "Noto Sans Khmer", Arial, Helvetica, sans-serif;
}

.totals-block__row {
  display: grid;
  grid-template-columns: 1fr 32mm;
  align-items: baseline;
  gap: 0 4mm;
  padding: 2px 0;
}

.totals-block__label {
  min-width: 0;
  white-space: nowrap;
}

.totals-block__value {
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.totals-block__row--top {
  border-top: 1px solid #000;
  padding-top: 4px;
  margin-top: 2px;
}

.totals-block__row--bottom {
  border-bottom: 1px solid #000;
  padding-bottom: 4px;
  margin-bottom: 2px;
}

.totals-block__row--strong {
  font-weight: 700;
}

.totals-block__row--footer {
  padding-top: 2px;
  font-size: 9px;
}
</style>
