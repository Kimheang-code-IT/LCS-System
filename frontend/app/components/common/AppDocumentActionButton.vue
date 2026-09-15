<script setup lang="ts">
import type { FreightAction } from '~/config/freight-modules'
import { documentActionButtonUi } from '~/utils/layout/document-action-button'

const props = withDefaults(defineProps<{
  label: string
  icon?: string
  color?: FreightAction['color']
  loading?: boolean
  disabled?: boolean
  to?: string
}>(), {
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  click: []
}>()

const ui = computed(() => documentActionButtonUi(props.color))
</script>

<template>
  <UButton
    v-bind="ui"
    size="sm"
    class="rounded-md"
    :icon="icon"
    :label="label"
    :loading="loading"
    :disabled="disabled"
    :to="to"
    @click="emit('click')"
  />
</template>
