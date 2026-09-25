import type { SourcePermission } from '~/types/lcs/domain'

export interface AuthUser {
  id?: number
  name: string
  email: string
  role?: string
  avatar?: string
  permissions?: string[]
  pageAccess?: string[]
  sourcePermissions?: SourcePermission[]
}
