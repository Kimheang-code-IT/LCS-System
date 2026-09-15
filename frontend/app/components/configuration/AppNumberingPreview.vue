<script setup lang="ts">
import type { RecordTypeNumbering } from '~/types/docetra/configuration'
import { previewRecordNumber } from '~/types/docetra/configuration'

const props = defineProps<{
  numbering: RecordTypeNumbering
}>()

const preview = computed(() => previewRecordNumber(props.numbering, 1))
</script>

<template>
  <div class="rounded-lg border border-dashed border-default bg-muted/30 px-4 py-3">
    <p class="text-xs text-muted">
      {{ $t('docetra.config.numberPreview') }}
    </p>
    <p class="mt-1 font-mono text-lg font-semibold tracking-wide text-highlighted">
      {{ preview }}
    </p>
  </div>
</template>
