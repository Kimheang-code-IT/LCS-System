<script setup lang="ts">
import { useTelegramRepository } from '~/repositories'
import { apiErrorMessage } from '~/utils/validation/api-error'
import type { TelegramDeliveryHistory } from '~/types/settings'

defineProps<{ canManage: boolean }>()
const { t } = useI18n()
const repo = useTelegramRepository()
const data = ref<TelegramDeliveryHistory | null>(null)
const pending = ref(false)
const error = ref('')
const page = ref(1)
const filters = reactive({ category: '', status: '', destination_type: '', date_from: '', date_to: '' })
async function load() {
  pending.value = true
  error.value = ''
  try {
    data.value = await repo.history({ ...filters, date_from: filters.date_from ? `${filters.date_from}T00:00:00Z` : '', date_to: filters.date_to ? `${filters.date_to}T23:59:59Z` : '', page: page.value, page_size: 20 })
  }
  catch (err) { error.value = apiErrorMessage(err, t('telegram.failed')) }
  finally { pending.value = false }
}
async function retry(id: number) {
  pending.value = true
  try { await repo.retry(id); await load() }
  catch (err) { error.value = apiErrorMessage(err, t('telegram.failed')); pending.value = false }
}
watch(page, load)
onMounted(load)
</script>

<template>
  <UCard>
    <template #header><h2 class="font-semibold">{{ t('telegram.history') }}</h2></template>
    <UAlert
v-if="error"
color="error"
:description="error"
class="mb-4" />
    <p v-if="data" class="mb-3 text-sm text-muted">{{ t('telegram.linkedUsers') }}: {{ data.linkedUsers }} · {{ t('telegram.lastSent') }}: {{ data.lastSentAt || '—' }} · {{ t('telegram.lastFailed') }}: {{ data.lastFailedAt || '—' }}</p>
    <form class="mb-4 grid gap-3 sm:grid-cols-3" @submit.prevent="page = 1; load()">
      <UFormField v-for="key in ['category', 'status', 'destination_type'] as const" :key="key" :label="t(`telegram.${key}`)">
        <USelect v-model="filters[key]" :items="[{ label: t('telegram.all'), value: '' }, ...(key === 'category' ? ['security', 'backup', 'system', 'private', 'recovery'] : key === 'status' ? ['PENDING', 'PROCESSING', 'SENT', 'FAILED', 'CANCELLED'] : ['PRIVATE', 'ADMIN']).map(value => ({ label: value, value }))]" class="w-full" />
      </UFormField>
      <UFormField v-for="key in ['date_from', 'date_to'] as const" :key="key" :label="t(`telegram.${key}`)">
        <UInput v-model="filters[key]" type="date" class="w-full" />
      </UFormField>
      <UButton
type="submit"
:loading="pending"
:label="t('telegram.filter')"
class="self-end justify-center" />
    </form>
    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead><tr><th v-for="key in ['date', 'category', 'event', 'destination_type', 'status', 'attempts']" :key="key" class="p-2">{{ t(`telegram.${key}`) }}</th><th /></tr></thead>
        <tbody>
          <tr v-for="item in data?.items" :key="item.id" class="border-t border-default">
            <td class="p-2">{{ item.createdAt }}</td><td class="p-2">{{ item.category }}</td><td class="p-2">{{ item.event }}</td><td class="p-2">{{ item.destination }}</td><td class="p-2">{{ item.status }}<p v-if="item.error" class="text-xs text-error">{{ item.error }}</p></td><td class="p-2">{{ item.attempts }}</td>
            <td class="p-2"><UButton
v-if="canManage && item.canRetry"
size="xs"
:disabled="pending"
:label="t('telegram.retry')"
@click="retry(item.id)" /></td>
          </tr>
        </tbody>
      </table>
      <p v-if="data && !data.items.length" class="p-4 text-sm text-muted">{{ t('telegram.noHistory') }}</p>
    </div>
    <UPagination
v-if="data"
v-model:page="page"
:total="data.meta.total"
:items-per-page="20"
class="mt-4" />
  </UCard>
</template>
