/**
 * Service Charge domain helpers shared by the standalone page and the Service
 * Order tab. The Fee Lines grid itself lives in the `jobCharges` module config
 * and is rendered by `AppLineTable`; this file only keeps the rules that both
 * hosts must agree on.
 */

export type ServiceChargeRow = Record<string, unknown>

/** `ServiceOrderCharge.status` values the backend allows deleting. */
export const DELETABLE_CHARGE_STATUS = 'DRAFT'

export function isDeletableCharge(row: ServiceChargeRow): boolean {
  // The API returns the display form ("Draft"); compare on the domain value.
  return String(row.status || '').toUpperCase() === DELETABLE_CHARGE_STATUS
}
