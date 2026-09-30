export function hasArchivePermission(
  sourcePermissions: readonly string[] | null | undefined,
  permission: 'archive.view' | 'archive.restore' | 'archive.hard_delete',
) {
  const granted = sourcePermissions || []
  return granted.includes('ALL_PAGES') || granted.includes(permission)
}

export function confirmsArchiveHardDelete(value: string) {
  return value === 'DELETE'
}
