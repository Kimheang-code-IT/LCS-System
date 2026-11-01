<script setup lang="ts">
import type { FreightAction } from '~/config/freight-modules'
import { documentActionButtonUi } from '~/utils/layout/document-action-button'

const props = withDefaults(defineProps<{
  /** Omitted for icon-only header actions (refresh, overflow menu trigger). */
  label?: string
  icon?: string
  /** 'primary' (dark), 'error' (red destructive), anything else = grey secondary. */
  color?: 'primary' | 'secondary' | 'destructive' | FreightAction['color']
  loading?: boolean
  disabled?: boolean
  to?: string
  square?: boolean
  ariaLabel?: string
  /** Rotate the button's own icon (Refresh pattern) instead of swapping in a spinner. */
  spinIcon?: boolean
}>(), {
  label: '',
  icon: '',
  color: 'primary',
  to: '',
  loading: false,
  disabled: false,
  square: false,
  ariaLabel: '',
  spinIcon: false,
})

const emit = defineEmits<{
  click: []
}>()

const ui = computed(() => documentActionButtonUi(props.color))
/** ~800ms clockwise revolution, linear, skipped for reduced-motion users. */
const spinIconUi = computed(() => props.spinIcon
  ? { leadingIcon: 'motion-safe:animate-spin motion-safe:[animation-duration:800ms]' }
  : undefined)
</script>

<template>
  <UButton
    :color="ui.color"
    :variant="ui.variant"
    :class="['rounded-md', ui.class]"
    :icon="spinIcon ? '' : icon"
    :ui="spinIconUi"
    :label="label"
    :loading="loading"
    :disabled="disabled"
    :to="to"
    :square="square"
    :aria-label="ariaLabel || undefined"
    @click="emit('click')"
  />
</template>
