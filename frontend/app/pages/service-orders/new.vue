<script setup lang="ts">
/**
 * Manual Service Order creation is retired: every order must come from a
 * quotation through Convert to Service Order. The old creation route sends the
 * user to the quotations list with that guidance instead of showing the form.
 */
definePageMeta({ titleKey: 'freight.pages.serviceOrders', permission: 'operations.service_orders.view' })

const { t } = useI18n()
const toast = useToast()

onMounted(async () => {
  toast.add({ title: t('freight.ui.serviceOrderNeedsQuotation'), color: 'warning' })
  await navigateTo('/quotations', { replace: true })
})
</script>

<template>
  <FreightJobEmptyState
    :title="t('freight.ui.serviceOrderNeedsQuotation')"
    icon="i-lucide-file-plus" />
</template>
