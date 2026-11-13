<script setup lang="ts">
definePageMeta({ titleKey: 'freight.pages.accountingPeriods', permission: 'finance.accounting_periods.view' })
const route = useRoute()
await navigateTo({ path: `/finance/accounting-periods/${String(route.params.id)}`, query: route.query }, { replace: true })
</script>
<template><span /></template>
