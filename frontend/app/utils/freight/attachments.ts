import { useLcsRepositories, useSettingsRepositories } from '~/repositories'
import { createClientId } from '~/utils/client-id'
import { hasSourcePermission } from '~/utils/freight/permissions'
import { apiErrorMessage } from '~/utils/validation/api-error'
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

const DEFAULT_ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'docx', 'xlsx', 'csv']

/**
 * File picker state shared by every `kind: 'files'` table.
 *
 * When the host supplies an upload context the selected files are stored by the
 * attachment API and the returned row (with its URL/storage key) is what the
 * document saves. Without a context the legacy local-preview row is kept, so
 * pages that do not own a persisted record still behave as before.
 */
export function useFileAttachments(options: {
  /** Read at pick time: the document id may arrive after the table mounts. */
  upload?: () => { module: string, recordNo: string } | undefined
} = {}) {
  const inputRef = ref<HTMLInputElement | null>(null)
  const auth = useAuthStore()
  const toast = useToast()
  const { t } = useI18n()
  const maxMb = useState('max-upload-size-mb', () => 50)
  const allowedExtensions = useState<string[]>('allowed-upload-extensions', () => DEFAULT_ALLOWED_EXTENSIONS)
  const uploading = ref(false)
  /**
   * Rejected files are reported next to the file grid, not in a toast. The
   * accepted files are still added, so one bad file does not discard the rest
   * of the selection.
   */
  const rejected = ref<string[]>([])
  const maxSizeMb = computed(() => maxMb.value)

  onMounted(async () => {
    try {
      const config = await useSettingsRepositories().appConfig.get()
      const next = Number(config.general?.maxUploadSizeMb)
      if (Number.isFinite(next) && next > 0) maxMb.value = next
      const configured = config.security?.allowedUploadExtensions
      if (Array.isArray(configured) && configured.length) {
        allowedExtensions.value = configured
          .map(value => String(value).trim().toLowerCase().replace(/^\./, ''))
          .filter(Boolean)
      }
    }
    catch {
      /* keep defaults */
    }
  })

  function openPicker() {
    inputRef.value?.click()
  }

  function uploadedRow(meta: Record<string, unknown>, file: File, uploadedBy: string, uploadedAt: string) {
    const previewKey = createClientId('file')
    rememberFilePreview(previewKey, file)
    return {
      id: String(meta.id || ''),
      fileName: String(meta.fileName || meta.name || file.name),
      file: String(meta.fileName || meta.name || file.name),
      uploadedBy,
      uploadedAt: String(meta.uploadedAt || uploadedAt),
      uploadDate: String(meta.uploadedAt || uploadedAt).slice(0, 10),
      mimeType: String(meta.mimeType || mimeFromFileName(file.name, file.type)),
      fileSize: Number(meta.sizeBytes || file.size),
      url: meta.url,
      storageKey: meta.storageKey,
      note: String(meta.note || ''),
      previewKey,
    }
  }

  async function rowsFromInput(event: Event): Promise<Array<Record<string, unknown>>> {
    const input = event.target as HTMLInputElement
    const files = Array.from(input.files || [])
    input.value = ''
    const uploadedBy = String(auth.user?.name || t('freight.ui.currentUser'))
    const uploadedAt = new Date().toISOString()
    const acceptedFiles: File[] = []
    const errors: string[] = []
    for (const file of files) {
      if (file.size > maxMb.value * 1024 * 1024) {
        errors.push(`${file.name} — ${t('freight.ui.fileTooLarge', { size: maxMb.value })}`)
        continue
      }
      if (!allowedExtensions.value.includes(extensionOf(file.name))) {
        errors.push(`${file.name} — ${t('freight.ui.fileTypeRejected')}`)
        continue
      }
      acceptedFiles.push(file)
    }
    rejected.value = errors
    if (!acceptedFiles.length) return []

    const upload = options.upload?.()
    if (!upload) {
      const local = acceptedFiles.map(file => attachmentRowFromFile(file, uploadedBy, uploadedAt))
      toast.add({ title: t('freight.ui.fileUploaded'), color: 'success' })
      return local
    }

    uploading.value = true
    try {
      const repository = useLcsRepositories().attachments
      const rows: Array<Record<string, unknown>> = []
      for (const file of acceptedFiles) {
        const meta = await repository.upload(file, upload)
        rows.push(uploadedRow(meta as Record<string, unknown>, file, uploadedBy, uploadedAt))
      }
      toast.add({ title: t('freight.ui.fileUploaded'), color: 'success' })
      return rows
    }
    catch (error) {
      rejected.value = [...errors, apiErrorMessage(error, t('api.somethingWentWrong'))]
      return []
    }
    finally {
      uploading.value = false
    }
  }

  /**
   * Remove the stored file when the caller may delete attachments. The row is
   * detached from the document either way; without `attachment.delete` the
   * stored object stays for audit instead of being destroyed.
   */
  async function removeUploaded(row: Record<string, unknown>) {
    const id = String(row.id || '')
    if (!id || !hasSourcePermission(auth.user, 'attachment.delete')) return
    try {
      await useLcsRepositories().attachments.remove([id])
    }
    catch (error) {
      rejected.value = [apiErrorMessage(error, t('api.somethingWentWrong'))]
    }
  }

  return { inputRef, openPicker, rowsFromInput, rejected, maxSizeMb, uploading, removeUploaded }
}
