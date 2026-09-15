import type { FreightRecord } from '~/types/freight/record'
import type { LcsPaged } from '~/types/lcs/domain'

export interface ModuleListQuery {
  q?: string
  filters?: Record<string, string | string[]>
  page?: number
  page_size?: number
  paginate?: boolean
  dateField?: string
  dateFrom?: string
  dateTo?: string
  sortKey?: string
  sortDir?: 'asc' | 'desc'
}

export interface ModuleRepository<T = FreightRecord> {
  list: (query?: ModuleListQuery) => Promise<LcsPaged<T>>
  get: (id: string) => Promise<T>
  create: (input: Record<string, unknown>) => Promise<T>
  update: (id: string, input: Record<string, unknown>) => Promise<T>
  remove: (ids: string[]) => Promise<void>
}
