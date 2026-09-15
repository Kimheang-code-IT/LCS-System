import type { FreightRecord } from '~/types/freight/record'

export function useJobRelated(jobNo: MaybeRefOrGetter<string>) {
  const store = useFreightStore()
  const no = computed(() => String(toValue(jobNo) || '').trim())

  function byJob(collection: string) {
    return computed<FreightRecord[]>(() => {
      if (!no.value) return []
      return store.list(collection).filter(row => String(row.jobNo || '') === no.value)
    })
  }

  const shipments = byJob('shipments')
  const customs = byJob('customs')
  const documents = byJob('documents')
  const deliveries = byJob('deliveries')
  const charges = byJob('jobCharges')
  const supplierCosts = byJob('supplierCosts')
  const payments = byJob('customerPayments')
  const supplierPayments = byJob('supplierPayments')
  const debitNotes = byJob('debitNotes')
  const receivables = byJob('receivables')
  const payables = byJob('payables')
  const journals = byJob('journals')
  const containerRequirements = byJob('containerRequirements')
  const actualContainers = byJob('actualContainers')

  const shipment = computed(() => shipments.value[0] || null)
  const customsRecord = computed(() => customs.value[0] || null)
  const delivery = computed(() => deliveries.value[0] || null)
  const profitability = computed(() => {
    if (!no.value) return null
    return store.list('profitability').find(row => String(row.jobNo || '') === no.value) || null
  })

  return {
    shipments,
    shipment,
    customs,
    customsRecord,
    documents,
    deliveries,
    delivery,
    charges,
    supplierCosts,
    payments,
    supplierPayments,
    debitNotes,
    receivables,
    payables,
    profitability,
    journals,
    containerRequirements,
    actualContainers,
  }
}
