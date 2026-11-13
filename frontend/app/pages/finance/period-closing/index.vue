<script setup lang="ts">
definePageMeta({ titleKey: 'freight.pages.accountingPeriods', permission: 'finance.accounting_periods.view' })
await navigateTo({ path: '/finance/accounting-periods', query: useRoute().query }, { replace: true })
</script>
<template><span /></template>
