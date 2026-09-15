<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { PrintViewModel } from '~/utils/freight/print-model'
import { printOrDash } from '~/utils/freight/print-model'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { DEBIT_NOTE_APPROVAL_SLOTS } from '~/config/print-templates'

const props = defineProps<{
  model: PrintViewModel
  printDate: string
  printUser: string
}>()

const { t } = useI18n()
const { formatDate, formatMoney, formatNumber } = useAppLocalization()

const money = (value: number) => formatMoney(value, props.model.totals.currency)
const qty = (value: number) => value ? formatNumber(value, { minimumFractionDigits: 3, maximumFractionDigits: 3 }) : ''
const unitPrice = (value: number) => value ? formatNumber(value, { minimumFractionDigits: 3, maximumFractionDigits: 3 }) : ''

type Row = Record<string, string>

const lineReference = computed(() =>
  printOrDash(props.model.shipment.blNo || props.model.shipment.workNo),
)

const rows = computed<Row[]>(() => {
  const lineRows = props.model.lines.map(line => ({
    reference: line.reference || lineReference.value,
    description: line.description || '',
    quantity: qty(line.quantity),
    unit: line.unit || 'CONT',
    unitPrice: unitPrice(line.unitPrice),
    currency: props.model.totals.currency,
    debit: line.debit ? money(line.debit) : '0.00',
    credit: line.credit ? money(line.credit) : '0.00',
  }))
  lineRows.push({
    reference: '',
    description: t('freight.print.fields.total'),
    quantity: '',
    unit: '',
    unitPrice: '',
    currency: props.model.totals.currency,
    debit: money(props.model.totals.totalDebit),
    credit: money(props.model.totals.totalCredit),
  })
  return lineRows
})

const columns = computed<TableColumn<Row>[]>(() => [
  { accessorKey: 'reference', header: t('freight.print.fields.blNo'), meta: { class: { td: 'w-[22mm]', th: 'w-[22mm]' } } },
  { accessorKey: 'description', header: t('freight.print.fields.description') },
  { accessorKey: 'quantity', header: t('freight.print.fields.quantity'), meta: { class: { td: 'text-end tabular-nums w-[14mm]', th: 'text-end w-[14mm]' } } },
  { accessorKey: 'unit', header: t('freight.print.fields.unit'), meta: { class: { td: 'w-[12mm] text-center', th: 'w-[12mm] text-center' } } },
  { accessorKey: 'unitPrice', header: t('freight.print.fields.unitPriceShort'), meta: { class: { td: 'text-end tabular-nums w-[18mm]', th: 'text-end w-[18mm]' } } },
  { accessorKey: 'currency', header: t('freight.print.fields.currency'), meta: { class: { td: 'w-[10mm] text-center', th: 'w-[10mm] text-center' } } },
  { accessorKey: 'debit', header: t('freight.print.fields.debit'), meta: { class: { td: 'text-end tabular-nums w-[18mm]', th: 'text-end w-[18mm]' } } },
  { accessorKey: 'credit', header: t('freight.print.fields.credit'), meta: { class: { td: 'text-end tabular-nums w-[18mm]', th: 'text-end w-[18mm]' } } },
])

const containerLabel = computed(() => {
  const qtyValue = props.model.shipment.packageQty
  const type = props.model.shipment.containerType || props.model.shipment.packageUnit
  if (qtyValue && type) return `${qtyValue} x ${type}`
  return printOrDash(type || qtyValue)
})

const packageLabel = computed(() => {
  const qtyValue = props.model.shipment.packageQty
  const unit = props.model.shipment.packageUnit
  if (qtyValue && unit) return `${qtyValue} ${unit}`
  return printOrDash(unit || qtyValue)
})

const partnerAddress = computed(() => {
  const lines: string[] = []
  if (props.model.party.address) {
    lines.push(props.model.party.address)
  }
  if (props.model.party.taxIdentifier) {
    lines.push(`TAX: ${props.model.party.taxIdentifier}`)
  }
  return lines.join('\n') || '-'
})

const partnerFields = computed(() => [
  { label: t('freight.print.fields.partner'), value: printOrDash(props.model.party.legalName || props.model.party.name) },
  { label: t('freight.print.fields.address'), value: partnerAddress.value },
])

const approvalRoles = computed(() => DEBIT_NOTE_APPROVAL_SLOTS.map(key => t(key)))

const documentMetaFields = computed(() => [
  { label: t('freight.print.fields.dcNoteNo'), value: printOrDash(props.model.document.number), strong: true },
  { label: t('freight.print.fields.billingDate'), value: props.model.document.issueDate ? formatDate(props.model.document.issueDate) : '' },
  { label: t('freight.print.fields.dueDate'), value: props.model.document.dueDate ? formatDate(props.model.document.dueDate) : '' },
])

const contactFields = computed(() => [
  { label: t('freight.print.fields.personInCharge'), value: props.model.document.personInCharge || props.model.party.contact || '' },
  { label: t('freight.print.fields.telNo'), value: props.model.party.phone || '' },
  { label: t('freight.print.fields.faxNo'), value: '' },
  { label: t('freight.print.fields.email'), value: props.model.party.email || '' },
])

function formatDateIso(value: string): string {
  const match = String(value || '').match(/^(\d{4}-\d{2}-\d{2})/)
  return match?.[1] || (value ? formatDate(value) : '-')
}

const shipmentColLeft = computed(() => [
  { label: t('freight.print.fields.workNo'), value: printOrDash(props.model.shipment.workNo) },
  { label: t('freight.print.fields.houseNo'), value: printOrDash(props.model.shipment.houseNo) },
  { label: t('freight.print.fields.masterNo'), value: printOrDash(props.model.shipment.masterNo) },
  { label: t('freight.print.fields.loadingPortShort'), value: printOrDash(props.model.shipment.loadingPort) },
  { label: t('freight.print.fields.dischargePortShort'), value: printOrDash(props.model.shipment.dischargePort) },
  { label: t('freight.print.fields.containerNo'), value: printOrDash(props.model.shipment.containerNo) },
])

const shipmentColMiddle = computed(() => [
  { label: t('freight.print.fields.etdShort'), value: props.model.shipment.etd ? formatDateIso(props.model.shipment.etd) : '-' },
  { label: t('freight.print.fields.etaShort'), value: props.model.shipment.eta ? formatDateIso(props.model.shipment.eta) : '-' },
  { label: t('freight.print.fields.vessel'), value: printOrDash(props.model.shipment.vessel) },
  { label: t('freight.print.fields.containerShort'), value: containerLabel.value },
])

const shipmentColRight = computed(() => [
  { label: t('freight.print.fields.invoiceDateShort'), value: props.model.document.issueDate ? formatDateIso(props.model.document.issueDate) : '-' },
  { label: t('freight.print.fields.package'), value: packageLabel.value },
  { label: t('freight.print.fields.voyage'), value: printOrDash(props.model.shipment.voyage) },
])

const partyBottomRow = computed(() => [
  { label: t('freight.print.fields.shipper'), value: printOrDash(props.model.shipment.shipper) },
  { label: t('freight.print.fields.consignee'), value: printOrDash(props.model.shipment.consignee) },
  { label: t('freight.print.fields.notifyPartyShort'), value: printOrDash(props.model.shipment.notifyParty) },
])

</script>

<template>
  <div class="print-paper print-paper--portrait">
    <header class="dcn-header">
      <PrintIssuerHeader :issuer="model.issuer" show-khmer />
      <hr class="dcn-header__separator">
    </header>

    <h1 class="dcn-title">
      {{ t('freight.print.title.debitNote') }}
    </h1>

    <section class="dcn-top-grid">
      <table class="dcn-approval-table">
        <tbody>
          <tr>
            <td rowspan="2" class="dcn-approval-table__sign">
              <span
                v-for="letter in t('freight.print.fields.sign').split('')"
                :key="letter"
                class="dcn-approval-table__sign-letter"
              >{{ letter }}</span>
            </td>
            <th
              v-for="role in approvalRoles"
              :key="role"
              class="dcn-approval-table__role"
              scope="col"
            >
              {{ role }}
            </th>
          </tr>
          <tr>
            <td
              v-for="role in approvalRoles"
              :key="`sig-${role}`"
              class="dcn-approval-table__cell"
            />
          </tr>
        </tbody>
      </table>

      <PrintMetaGrid variant="dcn-side" :items="documentMetaFields" />
    </section>

    <section class="dcn-partner-grid">
      <div class="dcn-partner-left">
        <PrintMetaGrid variant="dcn" :items="partnerFields" />
        <div class="dcn-contact-row">
          <span>{{ t('freight.print.fields.personInCharge') }} :</span>
          <span>{{ t('freight.print.fields.telNo') }} :</span>
          <span>{{ t('freight.print.fields.faxNo') }} :</span>
        </div>
      </div>

      <PrintMetaGrid variant="dcn-side" :items="contactFields" />
    </section>

    <section class="dcn-shipment-grid">
      <div class="dcn-shipment-col">
        <PrintMetaGrid variant="dcn-shipment" :items="shipmentColLeft" />
      </div>
      <div class="dcn-shipment-col">
        <PrintMetaGrid variant="dcn-shipment" :items="shipmentColMiddle" />
      </div>
      <div class="dcn-shipment-col">
        <PrintMetaGrid variant="dcn-shipment" :items="shipmentColRight" />
      </div>
    </section>

    <section class="dcn-party-grid">
      <PrintMetaGrid
        v-for="item in partyBottomRow"
        :key="`party-${item.label}`"
        variant="dcn-shipment"
        :items="[item]"
      />
    </section>

    <PrintLinesTable :columns="columns" :rows="rows" />

    <section class="mt-2 space-y-1">
      <div class="flex items-baseline justify-end gap-2 text-[11px] font-semibold text-gray-900">
        <span>{{ t('freight.print.fields.balanceAmount') }} {{ model.totals.currency }}</span>
        <span class="min-w-[24mm] text-right tabular-nums">{{ money(model.totals.balance) }}</span>
      </div>
      <p class="text-right text-[10px] font-medium uppercase tracking-wide text-gray-800">
        {{ model.amountInWords }}
      </p>
      <p v-if="model.document.remarks" class="text-[10px] text-gray-900">
        <span class="font-semibold">{{ t('freight.print.fields.remarks') }}</span>
        <span class="ml-1">{{ model.document.remarks }}</span>
      </p>
    </section>

    <section class="mt-3 flex flex-wrap items-start justify-between gap-4">
      <PrintBankBlock
        v-if="model.settlement.accountName || model.settlement.bankName"
        :settlement="model.settlement"
        :title="t('freight.print.fields.bankInfo')"
      />
      <div class="text-center text-[10px] text-gray-900">
        <p class="mb-1 font-semibold">{{ t('freight.print.fields.signedBy') }}</p>
        <div class="mx-auto w-[42mm] border-b border-gray-800" aria-hidden="true" />
      </div>
    </section>

    <PrintFooterBar
      :document-number="model.document.number"
      :print-date="props.printDate"
      :print-user="props.printUser"
    />
  </div>
</template>

<style>
@page debitNote {
  size: A4 portrait;
  margin: 10mm 10mm 12mm;
}
</style>

<style scoped>
.print-paper {
  page: debitNote;
  color: #111827;
}

.dcn-header {
  margin-bottom: 2mm;
}

.dcn-header__separator {
  margin: 6px 0 0;
  border: 0;
  border-top: 1.5px solid #1e4f8a;
}

.dcn-title {
  margin: 3mm 0;
  text-align: center;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #111827;
}

.dcn-top-grid,
.dcn-partner-grid {
  display: grid;
  grid-template-columns: 1fr 52mm;
  gap: 4mm;
  align-items: start;
}

.dcn-top-grid {
  margin-bottom: 2mm;
}

.dcn-partner-grid {
  margin-bottom: 2mm;
}

.dcn-partner-left {
  min-width: 0;
}

.dcn-side-block {
  width: 100%;
  margin: 0;
  justify-self: end;
}

.dcn-approval-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 9px;
  color: #111827;
}

.dcn-approval-table th,
.dcn-approval-table td {
  border: 1px solid #6b7280;
  padding: 2px 3px;
  text-align: center;
  vertical-align: middle;
}

.dcn-approval-table__sign {
  width: 7mm;
  padding: 2px 1px;
  font-weight: 700;
  line-height: 1;
  background: #fff;
}

.dcn-approval-table__sign-letter {
  display: block;
  line-height: 1.05;
}

.dcn-approval-table__role {
  height: 5mm;
  padding: 2px 1px;
  font-size: 8px;
  font-weight: 700;
  line-height: 1.15;
  white-space: normal;
  background: #fff;
}

.dcn-approval-table__cell {
  height: 10mm;
  padding: 0;
  background: #fff;
}


.dcn-shipment-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 52mm;
  gap: 4mm 6mm;
  align-items: start;
  margin-bottom: 2mm;
}

.dcn-shipment-col {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.dcn-party-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 52mm;
  gap: 4mm 6mm;
  margin-bottom: 2mm;
}

.dcn-field--shipment {
  grid-template-columns: 22mm 1fr;
}

.dcn-contact-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
  flex-wrap: nowrap;
  gap: 3mm;
  margin-top: 2px;
  font-size: 10px;
  line-height: 1.35;
  color: #111827;
}

.dcn-field--side {
  grid-template-columns: 22mm 1fr;
  gap: 0 1mm;
  width: 100%;
}

.dcn-field--side dt {
  color: #111827;
}

.dcn-field--side dd {
  margin: 0;
  min-width: 0;
  word-break: break-word;
}

.dcn-field__value--strong {
  font-weight: 700;
}

.dcn-field {
  display: grid;
  grid-template-columns: 26mm 1fr;
  align-items: baseline;
  gap: 0 2mm;
  font-size: 10px;
  line-height: 1.35;
  color: #111827;
}

.dcn-field dt {
  color: #374151;
}

.dcn-field dd {
  margin: 0;
  min-width: 0;
  word-break: break-word;
}

.dcn-field dt::after {
  content: ' :';
}
</style>
