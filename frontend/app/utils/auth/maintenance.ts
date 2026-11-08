/** Navigation UX only; the API owns maintenance admission and Casbin authorization. */
export function maintenanceRecoveryPath(path: string) {
  return ['/maintenance', '/auth/login', '/auth/change-password', '/administration/system-settings'].includes(path.replace(/\/$/, '') || '/')
}

export function redirectForMaintenance(status: number, code: unknown, path: string) {
  return status === 503 && code === 'MAINTENANCE_MODE' && !maintenanceRecoveryPath(path)
}
