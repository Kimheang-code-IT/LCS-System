<script setup lang="ts">
import type { PrintIssuer } from '~/utils/freight/print-model'
import { usePrintBilingual } from '~/composables/print/usePrintBilingual'

withDefaults(defineProps<{ issuer: PrintIssuer, showKhmer?: boolean }>(), {
  showKhmer: true,
})

const logoFailed = ref(false)
const { biInline } = usePrintBilingual()
</script>

<template>
  <div class="issuer-header">
    <div v-if="issuer.logoUrl && !logoFailed" class="issuer-header__logo">
      <img
        :src="issuer.logoUrl"
        :alt="issuer.legalName || issuer.displayName || 'issuer logo'"
        class="issuer-header__logo-img"
        @error="logoFailed = true"
      >
    </div>

    <div class="issuer-header__body">
      <p v-if="showKhmer && issuer.legalNameKh" class="issuer-header__name-kh font-khmer">
        {{ issuer.legalNameKh }}
      </p>
      <p class="issuer-header__name-en">
        {{ issuer.legalName || issuer.displayName }}
      </p>

      <p v-if="issuer.taxIdentifier" class="issuer-header__meta">
        <template v-if="showKhmer">
          <span class="font-khmer">{{ $t('freight.print.fields.vatTinKh', {}, { locale: 'km' }) }}</span>
          ({{ $t('freight.print.fields.vatTin') }}) {{ issuer.taxIdentifier }}
        </template>
        <template v-else>
          {{ $t('freight.print.fields.vatTin') }}: {{ issuer.taxIdentifier }}
        </template>
      </p>

      <p v-if="showKhmer && issuer.addressKh" class="issuer-header__meta font-khmer">
        {{ issuer.addressKh }}
      </p>

      <p v-if="issuer.address" class="issuer-header__meta">
        {{ issuer.address }}
      </p>

      <p v-if="issuer.phone || issuer.email" class="issuer-header__contact">
        <span v-if="issuer.phone" class="issuer-header__contact-item">
          {{ biInline('freight.print.fields.telephoneNo') }} {{ issuer.phone }}
        </span>
        <span v-if="issuer.email" class="issuer-header__contact-item issuer-header__contact-item--email">
          {{ biInline('freight.print.fields.email') }}: {{ issuer.email }}
        </span>
      </p>
    </div>

    <div class="issuer-header__spacer" aria-hidden="true" />
  </div>
</template>

<style scoped>
.issuer-header {
  display: flex;
  align-items: flex-start;
  gap: 3mm;
}

.issuer-header__logo {
  flex: 0 0 28mm;
  width: 28mm;
}

.issuer-header__logo-img {
  display: block;
  width: 100%;
  height: auto;
  max-height: 28mm;
  object-fit: contain;
  object-position: left top;
}

.issuer-header__body {
  flex: 1;
  min-width: 0;
  text-align: center;
  color: #000;
}

.issuer-header__spacer {
  flex: 0 0 28mm;
  width: 28mm;
}

.issuer-header__name-kh {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.2;
}

.issuer-header__name-en {
  margin: 1px 0 0;
  font-family: Arial, Helvetica, "Segoe UI", sans-serif;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.25;
  text-transform: uppercase;
  letter-spacing: 0.01em;
}

.issuer-header__meta {
  margin: 2px 0 0;
  font-size: 9px;
  line-height: 1.45;
}

.issuer-header__contact {
  display: flex;
  flex-wrap: nowrap;
  justify-content: space-between;
  align-items: baseline;
  gap: 2mm;
  margin: 2px 0 0;
  font-size: 9px;
  line-height: 1.45;
  white-space: nowrap;
}

.issuer-header__contact-item {
  flex: 0 1 auto;
  min-width: 0;
  white-space: nowrap;
}

.issuer-header__contact-item--email {
  margin-left: auto;
  text-align: right;
}

.font-khmer {
  font-family: "Noto Sans Khmer", sans-serif;
}
</style>
