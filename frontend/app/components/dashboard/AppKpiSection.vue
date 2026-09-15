<script setup lang="ts">
export type DashboardKpiCard = {
  key: string
  title: string
  value: string | number
  to?: string
  hint?: string
}

withDefaults(defineProps<{
  title: string
  cards: DashboardKpiCard[]
  loading?: boolean
}>(), {
  loading: false,
})

const emit = defineEmits<{
  refresh: []
}>()
</script>

<template>
  <section class="shrink-0">
    <h2 class="px-0.5 text-[11px] font-semibold uppercase tracking-wide text-dimmed">
      {{ title }}
    </h2>
    <div class="mt-1 grid grid-cols-2 gap-2 lg:grid-cols-4">
      <DashboardAppSummaryCard
        v-for="card in cards"
        :key="card.key"
        :title="card.title"
        :value="card.value"
        :to="card.to"
        :loading="loading"
        @refresh="emit('refresh')"
      >
        <p v-if="card.hint && !loading" class="mt-1 text-xs text-muted">
          {{ card.hint }}
        </p>
      </DashboardAppSummaryCard>
    </div>
  </section>
</template>
