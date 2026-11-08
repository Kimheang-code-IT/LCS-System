<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { PrintViewModel } from '~/utils/freight/print-model'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { usePrintBilingual } from '~/composables/print/usePrintBilingual'

const props = defineProps<{
  model: PrintViewModel
  printDate: string
  printUser: string
}>()

const { t: translate } = useI18n()
const t = (key: string) => translate(key, {}, { locale: 'en' })
const { formatDate, formatNumber } = useAppLocalization()
const { bi, biInline, khmer } = usePrintBilingual()

const money = (value: number, currency = props.model.totals.currency) => {
  const precision = currency !== props.model.totals.currency ? props.model.totals.localPrecision ?? 2 : props.model.precision ?? 2
  return `${currency} ${formatNumber(value, { minimumFractionDigits: precision, maximumFractionDigits: precision })}`
}

function formatInvoiceDateSpaced(value: string): string {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!match) return value ? formatDate(value) : '-'
  const [, year = '', month = '', day = ''] = match
  const spaced = (part: string) => part.split('').join(' ')
  return `D ${spaced(day)} M ${spaced(month)} Y ${spaced(year)}`
}

const enterpriseValue = computed(() =>
  [props.model.party.nameKh, props.model.party.legalName || props.model.party.name].filter(Boolean).join('\n') || '-',
)

const addressValue = computed(() => props.model.party.address || '-')

const vatTinLabel = computed(() => {
  const kh = khmer('freight.print.fields.enterpriseVatTinKh')
  const en = `(${t('freight.print.fields.vatTin')})`
  return kh ? `${kh}\n${en}` : en
})

type CustomerRow = { label: string, value: string }

const customerRows = computed<CustomerRow[]>(() => [
  { label: bi('freight.print.fields.enterpriseName'), value: enterpriseValue.value },
  { label: bi('freight.print.fields.address'), value: addressValue.value },
  { label: bi('freight.print.fields.telephoneNo'), value: props.model.party.phone || '' },
  { label: vatTinLabel.value, value: props.model.party.taxIdentifier || '' },
].filter(row => row.value))

type Row = Record<string, string>

function formatDescription(line: { descriptionKh: string, description: string }): string {
  const parts = [line.descriptionKh, line.description].filter(Boolean)
  return parts.join('\n') || '-'
}

const rows = computed<Row[]>(() => props.model.lines.map(line => ({
  no: String(line.no),
  description: formatDescription(line),
  quantity: formatNumber(line.quantity, { maximumFractionDigits: 3 }),
  unitPrice: `${line.currency} ${formatNumber(line.unitPrice, { minimumFractionDigits: props.model.precision ?? 2, maximumFractionDigits: Math.max(4, props.model.precision ?? 2) })}`,
  amount: money(line.amount),
})))

const columns = computed<TableColumn<Row>[]>(() => [
  { accessorKey: 'no', header: bi('freight.print.fields.lineNo'), meta: { class: { td: 'text-center w-[5%]', th: 'w-[5%] text-center' } } },
  { accessorKey: 'description', header: bi('freight.print.fields.descriptionGoods'), meta: { class: { td: 'text-start w-[40%] whitespace-pre-line', th: 'w-[40%] text-center whitespace-pre-line' } } },
  { accessorKey: 'quantity', header: bi('freight.print.fields.quantity'), meta: { class: { td: 'text-center tabular-nums w-[14%]', th: 'w-[14%] text-center' } } },
  { accessorKey: 'unitPrice', header: bi('freight.print.fields.unitPrice'), meta: { class: { td: 'text-end tabular-nums w-[14%]', th: 'w-[14%] text-center' } } },
  { accessorKey: 'amount', header: bi('freight.print.fields.amount'), meta: { class: { td: 'text-end tabular-nums w-[27%]', th: 'w-[27%] text-center' } } },
])

const totalsItems = computed(() => {
  const totals = props.model.totals
  const items: Array<{
    label: string
    value: string
    strong?: boolean
    topRule?: boolean
    bottomRule?: boolean
    footer?: boolean
  }> = [
    { label: `${biInline('freight.print.fields.subTotal')} (${totals.currency})`, value: money(totals.subtotal) },
  ]
  if (totals.discount) {
    items.push({ label: biInline('freight.print.fields.discount'), value: money(totals.discount) })
    items.push({ label: biInline('freight.print.fields.taxableAmount'), value: money(totals.taxableAmount ?? totals.subtotal) })
  }
  if (totals.taxRate > 0 || totals.taxAmount > 0) {
    const rate = totals.taxRate ? ` @${formatNumber(totals.taxRate)}%` : ''
    items.push({
      label: `${biInline('freight.print.fields.vat')}${rate} (${totals.currency})`,
      value: money(totals.taxAmount),
    })
  }
  items.push({
    label: `${biInline('freight.print.fields.grandTotal')} (${totals.currency})`,
    value: money(totals.grandTotal),
    strong: true,
    topRule: true,
  })
  if (totals.exchangeRate > 0 && totals.localCurrency !== totals.currency) {
    items.push({
      label: `${biInline('freight.print.fields.grandTotal')} (${totals.localCurrency})`,
      value: money(totals.grandTotalLocal, totals.localCurrency),
      strong: true,
      topRule: true,
      bottomRule: true,
    })
    items.push({
      label: `${biInline('freight.print.fields.exchangeRate')} 1 ${totals.currency} =`,
      value: `${formatNumber(totals.exchangeRate, { maximumFractionDigits: 8 })} ${totals.localCurrency}`,
      footer: true,
    })
  }
  return items
})

const partyDisplayName = computed(() =>
  props.model.party.legalName || props.model.party.name || '-',
)
</script>

<template>
  <div class="tax-invoice print-paper print-paper--portrait">
    <div class="tax-invoice__content">
    <header class="tax-invoice__header">
      <PrintIssuerHeader :issuer="model.issuer" show-khmer />
      <hr class="tax-invoice__separator">
    </header>

    <div class="tax-invoice__title">
      <p class="tax-invoice__title-kh font-khmer">
        {{ khmer(model.document.titleKey || 'freight.print.title.invoice') }}
      </p>
      <p class="tax-invoice__title-en">
        {{ t(model.document.titleKey || 'freight.print.title.invoice') }}
      </p>
    </div>

    <section class="tax-invoice__meta">
      <p class="tax-invoice__customer-heading">
        <span class="font-khmer">{{ khmer('freight.print.fields.customerLabel') }}</span>
        <template v-if="khmer('freight.print.fields.customerLabel')">
          /
        </template>
        {{ t('freight.print.fields.customerLabel') }} :
      </p>

      <div class="tax-invoice__meta-body">
        <div class="tax-invoice__meta-left">
          <PrintMetaGrid variant="tax-invoice" :items="customerRows" />
        </div>

        <aside class="tax-invoice__meta-right">
          <div class="tax-invoice__side-field">
            <span class="tax-invoice__side-label whitespace-pre-line">{{ bi('freight.print.fields.invoiceNo') }}</span>
            <span class="tax-invoice__side-value">{{ model.document.number }}</span>
          </div>
          <div class="tax-invoice__side-field">
            <span class="tax-invoice__side-label whitespace-pre-line">{{ bi('freight.print.fields.date') }}</span>
            <span class="tax-invoice__side-value tax-invoice__date-value">{{ formatInvoiceDateSpaced(model.document.issueDate) }}</span>
          </div>
        </aside>
      </div>
    </section>

    <div class="tax-invoice__table-wrap">
      <PrintLinesTable variant="tax-invoice" :columns="columns" :rows="rows" />
    </div>

    <section class="tax-invoice__footer-grid">
      <div class="tax-invoice__footer-left">
        <PrintBankBlock
          v-if="model.settlement.accountName || model.settlement.bankName"
          variant="tax-invoice"
          :settlement="model.settlement"
        />
      </div>
      <div class="tax-invoice__footer-right">
        <PrintTotalsBlock :items="totalsItems" />
      </div>
    </section>

    <p v-if="model.document.remarks" class="tax-invoice__remarks">{{ biInline('freight.print.fields.remarks') }}: {{ model.document.remarks }}</p>
    <footer class="tax-invoice__signatures">
      <PrintSignatureBlock
        :slots="[
          {
            caption: bi('freight.print.fields.customerSignatureFull'),
            stampUrl: model.signatures.customerStampUrl || undefined,
            signatureUrl: model.signatures.customerSignatureUrl || undefined,
            name: partyDisplayName,
          },
          {
            caption: bi('freight.print.fields.sellerSignatureFull'),
            stampUrl: model.signatures.sellerStampUrl || undefined,
            signatureUrl: model.signatures.sellerSignatureUrl || undefined,
            name: model.issuer.legalName || model.issuer.displayName,
          },
        ]"
      />
    </footer>
    </div>

    <PrintFooterBar
      :document-number="model.document.number"
      :print-date="props.printDate"
      :print-user="props.printUser"
    />
  </div>
</template>

<style scoped>
.tax-invoice {
  display: flex;
  flex-direction: column;
  position: relative;
  width: 100%;
  max-width: 190mm;
  margin: 0 auto;
  padding: 0;
  font-family: Arial, Helvetica, "Noto Sans Khmer", "Noto Sans SC", sans-serif;
  font-size: 10px;
  line-height: 1.4;
  color: #000;
}

.tax-invoice__content {
  flex: 1 1 auto;
  min-height: 0;
}

.font-khmer {
  font-family: "Noto Sans Khmer", sans-serif;
}

.tax-invoice__header {
  margin-bottom: 8px;
}

.tax-invoice__separator {
  margin: 6px 0 0;
  border: 0;
  border-top: 1.5px solid #1e4f8a;
}

.tax-invoice__title {
  margin: 14px 0 18px;
  text-align: center;
}

.tax-invoice__title-kh {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
}

.tax-invoice__title-en {
  margin: 5px 0 0;
  font-family: "Times New Roman", Times, Georgia, serif;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.tax-invoice__meta {
  margin-bottom: 14px;
}

.tax-invoice__customer-heading {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  text-decoration: underline;
}

.tax-invoice__meta-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 56mm;
  align-items: flex-start;
  gap: 8mm;
}

.tax-invoice__meta-left {
  flex: 1 1 68%;
  min-width: 0;
}

.tax-invoice__meta-right {
  flex: 0 0 32%;
  min-width: 0;
  padding-right: 4mm;
}

.tax-invoice__side-field {
  display: flex;
  flex-wrap: nowrap;
  justify-content: flex-start;
  align-items: baseline;
  gap: 1.5mm;
  margin-bottom: 8px;
  font-size: 11px;
  line-height: 1.4;
  white-space: normal;
  overflow-wrap: anywhere;
}

.tax-invoice__side-field:last-child {
  margin-bottom: 0;
}

.tax-invoice__side-label::after {
  content: ' :';
}

.tax-invoice__side-value {
  font-size: 12px;
  font-weight: 500;
}

.tax-invoice__date-value {
  letter-spacing: 0.02em;
  font-variant-numeric: tabular-nums;
}

.tax-invoice__table-wrap {
  width: 100%;
  margin: 0 0 10px;
}

.tax-invoice__footer-grid {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6mm;
  break-inside: avoid;
  width: 100%;
  margin-top: 8px;
}

.tax-invoice__footer-left {
  flex: 0 1 48%;
  min-width: 0;
}

.tax-invoice__footer-right {
  flex: 0 1 52%;
  min-width: 0;
  margin-left: auto;
}

.tax-invoice__signatures {
  margin-top: 16mm;
  break-inside: avoid;
}

.tax-invoice__remarks { white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 4mm; }

@media print {
  .tax-invoice__content {
    padding-bottom: 10mm;
  }
}
</style>
