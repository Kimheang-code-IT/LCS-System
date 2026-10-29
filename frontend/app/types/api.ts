import type { ColumnFiltersState } from '@tanstack/vue-table'
import type { SourcePermission } from '~/types/domain'

export interface TableQueryParams {
  q?: string
  page: number
  limit: number
  sort?: string
  filters?: ColumnFiltersState
  startDate?: string
  endDate?: string
}

export interface AuthUser {
  id?: number
  name: string
  email: string
  /** Display label derived from the highest role (e.g. ``SuperAdmin``). */
  role?: string
  /** Every role code the account holds; authorization is their union. */
  roles?: string[]
  avatar?: string
  permissions?: string[]
  pageAccess?: string[]
  sourcePermissions?: SourcePermission[]
  /**
   * True when the password was set by an administrator. The API refuses every
   * route except changing it, and the middleware routes this session to the
   * change-password screen.
   */
  mustChangePassword?: boolean
}

declare module '#app' {
  interface PageMeta {
    permission?: string
    titleKey?: string
  }
}

export {}
