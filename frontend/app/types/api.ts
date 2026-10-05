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

export interface PaginatedResponse<T, S = Record<string, unknown>> {
  items: T[]
  total: number
  page: number
  limit: number
  summary?: S
}

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

declare module '#app' {
  interface PageMeta {
    permission?: string
    titleKey?: string
  }
}

export {}
