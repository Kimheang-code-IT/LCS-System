export const MASTER_DATA_PAGE_PERMISSION = 'master.reference.view'
export const SERVICE_ORDERS_PAGE_PERMISSION = 'operations.service_orders.view'

/** Resolve the page permission required for a route path. */
export function requiredPagePermissionForPath(path: string) {
  if (path === '/service-orders' || path.startsWith('/service-orders/')) {
    return SERVICE_ORDERS_PAGE_PERMISSION
  }
  if (path === '/master-data' || path.startsWith('/master-data/')) {
    return MASTER_DATA_PAGE_PERMISSION
  }
  return ''
}
