import type { FreightRecord } from '~/types/record'
import type { useConfirm } from '~/composables/common/useConfirm'
import { useLcs } from '~/composables/freight/useLcs'

type ConfirmFn = ReturnType<typeof useConfirm>['confirm']
type Toast = ReturnType<typeof useToast>

/**
 * Shared Re-Quotation flow (Service Orders list row menu and detail header):
 * confirm, then create an independent quotation through the backend
 * re-quotation (which copies party, route, requirements and the aggregated
 * pricing) and navigate to it. The remembered idempotency key answers a
 * network retry with the quotation already created; a later deliberate
 * re-quotation runs with a fresh key. The source order is never modified.
 */
export function useRequotation(options: {
  confirm: ConfirmFn
  setConfirmLoading: (loading: boolean) => void
  dismissConfirm: () => void
  toast: Toast
  onError: (message: string) => void
}) {
  const lcs = useLcs()
  const { t } = useI18n()

  async function requoteFromServiceOrder(orderId: string, orderNo: string): Promise<FreightRecord | null> {
    if (!orderId) return null
    const ok = await options.confirm({
      kind: 'submit',
      title: t('freight.ui.requoteTitle'),
      description: t('freight.ui.requoteDescription', { serviceOrderNo: orderNo }),
      confirmLabel: t('freight.ui.createQuotation'),
      confirmColor: 'primary',
      keepOpenOnConfirm: true,
    })
    if (!ok) return null
    options.setConfirmLoading(true)
    try {
      const created = await lcs.runCommand('quotations.requote', orderId, key =>
        lcs.quotations.createFromServiceOrder(orderId, key),
      )
      options.dismissConfirm()
      options.toast.add({
        title: t('freight.ui.requoteCreated', {
          quotationNo: String(created.quotationNo || ''),
          serviceOrderNo: orderNo,
        }),
        color: 'success',
      })
      await navigateTo(`/quotations/${String(created.id)}`)
      return created
    }
    catch (error) {
      options.dismissConfirm()
      options.onError(lcs.errorMessage(error))
      return null
    }
    finally {
      options.setConfirmLoading(false)
    }
  }

  return { requoteFromServiceOrder }
}
