import type { LcsPaged } from '~/types/lcs/domain'

export interface ArchiveRecord {
  [key: string]: unknown
  id: string
  entityType: string
  module: string
  entityId: string
  reference: string
  deletedById?: string | null
  deletedBy: string
  deletedAt: string
  originalOwnerId?: string | null
  originalOwner: string
  status: 'ARCHIVED'
  data?: Record<string, unknown>
}

export interface ArchiveListQuery {
  q?: string
  page?: number
  page_size?: number
  entity_type?: string
  deleted_by?: number
  dateFrom?: string
  dateTo?: string
}

export interface ArchiveOptions {
  entityTypes: Array<{ value: string, label: string }>
  deletedByUsers: Array<{ value: string, label: string }>
}

export interface ArchiveRepository {
  list: (query?: ArchiveListQuery) => Promise<LcsPaged<ArchiveRecord>>
  options: () => Promise<ArchiveOptions>
  get: (entityType: string, entityId: string) => Promise<ArchiveRecord>
  restore: (entityType: string, entityId: string) => Promise<void>
  hardDelete: (entityType: string, entityId: string) => Promise<void>
}
