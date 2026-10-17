import type { FreightRecord } from '~/types/record'
import type { LcsPaged } from '~/types/domain'
import type { RecordStatusPolicy } from '~/types/status'

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
  /** Legal status transitions for this collection, already permission-filtered. */
  statusPolicy: () => Promise<RecordStatusPolicy>
  /** Apply one plain status transition (activate / deactivate / mark / reopen). */
  changeStatus: (id: string, status: string, reason?: string) => Promise<T>
}
