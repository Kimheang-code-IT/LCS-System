/**
 * Global Cmd+K search types (keyword / semantic / AI citations).
 */

export type SearchMode = 'keyword' | 'semantic'

export type SearchEntityType =
  | 'navigation'
  | 'document'
  | 'incomingDocument'
  | 'outgoingDocument'
  | 'meeting'
  | 'meetingTopic'
  | 'file'
  | 'attachment'
  | 'company'
  | 'department'
  | 'officer'
  | 'user'
  | 'other'

export interface IndexedDocument {
  id: string
  entityType: SearchEntityType
  entityId: string
  title: string
  text: string
  url: string
  /** Entity permission code, e.g. portal.file_upload.view — empty = always visible when logged in */
  permission: string
  mimeType?: string
  updatedAt: string
}

export interface SearchHit extends IndexedDocument {
  score: number
  snippet: string
  sourceLabel: string
}

export interface AiSearchAnswer {
  answer: string
  citations: SearchHit[]
}

export interface SearchQueryOptions {
  limit?: number
}
