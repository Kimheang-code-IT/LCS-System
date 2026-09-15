import type { IndexedDocument, SearchEntityType } from '~/types/docetra/search'
import {
  isSearchIndexSeeded,
  markSearchIndexSeeded,
  upsertIndexedDocuments,
} from '~/utils/search/search-index'

export function ensureSearchIndexSeeded() {
  if (!import.meta.client) return
  if (isSearchIndexSeeded()) return
  upsertIndexedDocuments([] as IndexedDocument[])
  markSearchIndexSeeded()
}

export function sourceLabelFor(entityType: SearchEntityType): string {
  const map: Record<SearchEntityType, string> = {
    navigation: 'Navigation',
    document: 'Document',
    incomingDocument: 'Incoming',
    outgoingDocument: 'Outgoing',
    meeting: 'Meeting',
    meetingTopic: 'Topic',
    file: 'File',
    attachment: 'Attachment',
    company: 'Company',
    department: 'Department',
    officer: 'Officer',
    user: 'User',
    other: 'Record',
  }
  return map[entityType] || 'Record'
}
