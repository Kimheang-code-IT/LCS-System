import { useSettingsRepositories } from '~/repositories'
import { createClientId } from '~/utils/client-id'
import { safeExternalUrl, safeFilePreviewUrl } from '~/utils/security/url'

const MIME_BY_EXT: Record<string, string> = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  svg: 'image/svg+xml',
  txt: 'text/plain',
  md: 'text/plain',
  csv: 'text/csv',
  html: 'text/html',
  json: 'application/json',
  mp4: 'video/mp4',
  webm: 'video/webm',
  mp3: 'audio/mpeg',
  wav: 'audio/wav',
}

type PreviewCacheEntry = { url: string }

const previewCache = new Map<string, PreviewCacheEntry>()

function extensionOf(fileName: string) {
  const parts = fileName.toLowerCase().split('.')
  return parts.length > 1 ? parts[parts.length - 1]! : ''
}

export function mimeFromFileName(fileName: string, mimeType = '') {
  const mime = String(mimeType || '').trim()
  if (mime) return mime
  return MIME_BY_EXT[extensionOf(fileName)] || 'application/octet-stream'
}

export function attachmentRowFromFile(file: File, uploadedBy: string, uploadedAt = new Date().toISOString()) {
  const previewKey = createClientId('file')
  rememberFilePreview(previewKey, file)
  return {
    fileName: file.name,
    file: file.name,
    uploadedBy,
    uploadedAt,
    uploadDate: uploadedAt.slice(0, 10),
    mimeType: mimeFromFileName(file.name, file.type),
    fileSize: file.size,
    previewKey,
  }
}

export function fileTableRowName(row: Record<string, unknown>) {
  return String(row.fileName || row.file || row.documentNo || '').trim()
}

export function fileTableRowBy(row: Record<string, unknown>) {
  return String(row.uploadedBy || row.createdBy || '').trim()
}

export function fileTableRowCreated(row: Record<string, unknown>) {
  return String(row.uploadedAt || row.uploadDate || row.createdAt || '').trim()
}

/** Job Files tab uses the same attachment rows as quotations. Fall back to related documents. */
export function jobFileAttachments(
  job: Record<string, unknown>,
  documents: Array<Record<string, unknown>> = [],
) {
  const stored = Array.isArray(job.attachments) ? job.attachments : []
  if (stored.length) return stored as Array<Record<string, unknown>>
  return documents.map((row) => {
    const fileName = fileTableRowName(row)
    return {
      fileName,
      file: fileName,
      uploadedBy: fileTableRowBy(row),
      uploadedAt: fileTableRowCreated(row),
      mimeType: mimeFromFileName(fileName, String(row.mimeType || '')),
      fileSize: row.fileSize,
    }
  })
}

function canCreateObjectUrl() {
  return typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function'
}

function rememberFilePreview(key: string, source: Blob) {
  if (!canCreateObjectUrl()) return
  const previous = previewCache.get(key)
  if (previous) URL.revokeObjectURL(previous.url)
  previewCache.set(key, { url: URL.createObjectURL(source) })
}

/** Only a real preview key (from an uploaded File) can resolve to a cached blob URL. */
function cacheKeyFor(row: Record<string, unknown>): string | null {
  const previewKey = String(row.previewKey || '').trim()
  return previewKey || null
}

/**
 * Object URL or http(s) URL for a native browser-tab preview. Returns null when
 * the row has no persisted URL and no real uploaded file content — previews are
 * never fabricated.
 */
export function filePreviewHref(row: Record<string, unknown>): string | null {
  const persisted = safeExternalUrl(row.url || row.fileUrl || row.href)
  if (persisted) return persisted
  const storedPreview = safeFilePreviewUrl(row.previewUrl)
  if (storedPreview && !storedPreview.startsWith('blob:')) return storedPreview
  if (!canCreateObjectUrl()) return null
  const key = cacheKeyFor(row)
  if (!key) return null
  return previewCache.get(key)?.url || null
}

export function revokeFilePreview(row: Record<string, unknown>) {
  const key = String(row.previewKey || '').trim()
  if (!key) return
  const cached = previewCache.get(key)
  if (!cached) return
  if (typeof URL.revokeObjectURL === 'function') URL.revokeObjectURL(cached.url)
  previewCache.delete(key)
}

export function useFileAttachments() {
  const inputRef = ref<HTMLInputElement | null>(null)
  const auth = useAuthStore()
  const toast = useToast()
  const { t } = useI18n()
  const maxMb = useState('max-upload-size-mb', () => 50)

  onMounted(async () => {
    try {
      const config = await useSettingsRepositories().appConfig.get()
      const next = Number(config.general?.maxUploadSizeMb)
      if (Number.isFinite(next) && next > 0) maxMb.value = next
    }
    catch {
      /* keep default */
    }
  })

  function openPicker() {
    inputRef.value?.click()
  }

  function rowsFromInput(event: Event) {
    const input = event.target as HTMLInputElement
    const files = Array.from(input.files || [])
    input.value = ''
    const uploadedBy = String(auth.user?.name || t('freight.ui.currentUser'))
    const uploadedAt = new Date().toISOString()
    const accepted: Array<Record<string, unknown>> = []
    for (const file of files) {
      if (file.size > maxMb.value * 1024 * 1024) {
        toast.add({ title: t('freight.ui.fileTooLarge', { size: maxMb.value }), description: file.name, color: 'error' })
        continue
      }
      accepted.push(attachmentRowFromFile(file, uploadedBy, uploadedAt))
    }
    if (accepted.length) toast.add({ title: t('freight.ui.fileUploaded'), color: 'success' })
    return accepted
  }

  return { inputRef, openPicker, rowsFromInput }
}
