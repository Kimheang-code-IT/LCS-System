<script setup lang="ts">
/**
 * Compact per-line adjustment dialog, opened from the row `...` menu of any
 * table configured with `lineDetails`. Only the two values the accounting model
 * stores per line: a discount amount and a tax rate.
 */
const props = withDefaults(defineProps<{
  open: boolean
  /** Quantity x unit price of the selected line, used to bound the discount. */
  maxDiscount?: number
  discount?: number
  taxRate?: number
  disabled?: boolean
}>(), {
  maxDiscount: 0,
  discount: 0,
  taxRate: 0,
  disabled: false,
})

const emit = defineEmits<{
  'update:open': [boolean]
  'save': [{ discount: number, taxRate: number }]
}>()

const { t } = useI18n()
const draftDiscount = ref(0)
const draftTaxRate = ref(0)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    draftDiscount.value = Number(props.discount) || 0
    draftTaxRate.value = Number(props.taxRate) || 0
  },
)

const discountError = computed(() => {
  const value = Number(draftDiscount.value) || 0
  if (value < 0) return t('freight.ui.discountNegative')
  if (props.maxDiscount > 0 && value > props.maxDiscount) return t('freight.ui.discountTooLarge')
  return ''
})

const taxRateError = computed(() => {
  const value = Number(draftTaxRate.value) || 0
  return value < 0 || value > 100 ? t('freight.ui.taxRateRange') : ''
})

const invalid = computed(() => Boolean(discountError.value || taxRateError.value))

function close() {
  emit('update:open', false)
}

function save() {
  if (props.disabled || invalid.value) return
  emit('save', {
    discount: Number(draftDiscount.value) || 0,
    taxRate: Number(draftTaxRate.value) || 0,
  })
  close()
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('freight.ui.lineAdditionalDetails')"
    :ui="{ content: 'max-w-md' }"
    @update:open="emit('update:open', $event)">
    <template #body>
      <div class="space-y-3">
        <UFormField :label="t('freight.fields.discount')" :error="discountError">
          <UInputNumber
            v-model="draftDiscount"
            :min="0"
            :max="maxDiscount > 0 ? maxDiscount : undefined"
            :increment="false"
            :decrement="false"
            :step-snapping="false"
            :disabled="disabled"
            class="w-full"
            :ui="{ base: 'text-right tabular-nums' }" />
        </UFormField>
        <UFormField :label="t('freight.ui.taxRatePct')" :error="taxRateError">
          <UInputNumber
            v-model="draftTaxRate"
            :min="0"
            :max="100"
            :increment="false"
            :decrement="false"
            :step-snapping="false"
            :disabled="disabled"
            class="w-full"
            :ui="{ base: 'text-right tabular-nums' }" />
        </UFormField>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="t('actions.cancel')"
          @click="close" />
        <UButton
          :label="t('actions.save')"
          :disabled="disabled || invalid"
          @click="save" />
      </div>
    </template>
  </UModal>
</template>
