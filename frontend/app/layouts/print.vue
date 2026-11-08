<template>
  <div class="print-layout min-h-dvh bg-default">
    <NuxtPage />
  </div>
</template>

<style>
@page {
  size: A4 portrait;
  margin: 10mm 10mm 15mm;
}
</style>

<style scoped>
@media print {
  :global(html),
  :global(body),
  :global(#__nuxt) {
    width: fit-content !important;
    height: auto !important;
    min-height: 0 !important;
  }

  .print-layout {
    width: fit-content !important;
    min-height: 0 !important;
  }
}
</style>
