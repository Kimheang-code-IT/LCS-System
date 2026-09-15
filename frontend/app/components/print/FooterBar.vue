<script setup lang="ts">
defineProps<{
  documentNumber: string
  printDate: string
  printUser: string
}>()
</script>

<template>
  <div class="print-footer">
    <span>{{ $t('freight.print.fields.printDate') }}: {{ printDate }}</span>
    <span class="font-medium">{{ documentNumber }}</span>
    <span>{{ $t('freight.print.fields.printUser') }}: {{ printUser }}</span>
  </div>
</template>

<style scoped>
.print-footer {
  display: flex;
  flex-shrink: 0;
  justify-content: space-between;
  align-items: center;
  gap: 4mm;
  margin-top: auto;
  padding-top: 8mm;
  font-size: 9px;
  line-height: 1.3;
  color: #374151;
}

@media print {
  .print-footer {
    position: fixed;
    bottom: 6mm;
    left: 10mm;
    right: 10mm;
    margin-top: 0;
    padding-top: 0;
  }
}
</style>
