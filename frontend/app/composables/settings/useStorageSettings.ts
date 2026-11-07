import { useSettingsRepositories } from '~/repositories'
import { useConfirm } from '~/composables/common/useConfirm'
import { apiErrorMessage } from '~/utils/validation/api-error'
import type { StorageJob, StorageOverview, StorageProviderStatus } from '~/types/settings'

/**
 * State + actions for the Storage & Backup panel. The page owns the config
 * form (schema-driven); this composable owns connection, backup, migration
 * and restore actions that do not fit the generic field schema.
 *
 * Failures render inline (`pageError` UAlert), not as toasts — the project's
 * toast policy reserves error toasts for the transport layer (useApi.ts).
 */
export function useStorageSettings() {
  const { storage } = useSettingsRepositories()
  const { t } = useI18n()
  const toast = useToast()
  const { confirm } = useConfirm()

  const providers = ref<Record<'r2' | 'gdrive', StorageProviderStatus> | null>(null)
  const overview = ref<StorageOverview | null>(null)
  const pageError = ref('')
  const loading = ref(false)
  const busy = ref(false)
  const pendingAction = ref(false)

  function fail(caught: unknown, fallback: string) {
    pageError.value = apiErrorMessage(caught, fallback)
  }

  async function load() {
    loading.value = true
    try {
      const status = await storage.status()
      providers.value = status.providers
      overview.value = status.overview
    }
    catch (error) {
      fail(error, t('lcs.common.loadFailed'))
    }
    finally {
      loading.value = false
    }
  }

  async function testConnection(provider: 'r2' | 'gdrive') {
    if (busy.value) return
    pageError.value = ''
    busy.value = true
    try {
      const result = await storage.testConnection(provider)
      if (result.status === 'connected') toast.add({ title: result.message, color: 'success' })
      else pageError.value = result.message || t('lcs.settings.storage.testFailed')
      await load()
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.testFailed'))
    }
    finally {
      busy.value = false
    }
  }

  async function connectGoogle() {
    if (busy.value) return
    pageError.value = ''
    busy.value = true
    try {
      const { url } = await storage.googleAuthorize()
      // Server-side OAuth popup; the backend callback persists the tokens.
      // When the popup closes (or the grant is revoked in it) the status is
      // re-read so the Connected/Connected-as card updates immediately.
      const popup = window.open(url, 'storage-google-oauth', 'popup,width=520,height=640')
      if (popup) {
        const poll = window.setInterval(() => {
          if (popup.closed) {
            window.clearInterval(poll)
            void load()
          }
        }, 1500)
        window.setTimeout(() => window.clearInterval(poll), 120_000)
      }
      toast.add({ title: t('lcs.settings.storage.oauthOpened'), color: 'info' })
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.connectFailed'))
    }
    finally {
      busy.value = false
    }
  }

  async function disconnectGoogle() {
    if (pendingAction.value) return
    const ok = await confirm({
      kind: 'generic',
      titleKey: 'lcs.settings.storage.disconnectTitle',
      descriptionKey: 'lcs.settings.storage.disconnectHelp',
    })
    if (!ok) return
    pageError.value = ''
    pendingAction.value = true
    try {
      await storage.googleDisconnect()
      toast.add({ title: t('lcs.settings.storage.disconnected'), color: 'success' })
      await load()
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.connectFailed'))
    }
    finally {
      pendingAction.value = false
    }
  }

  async function backupNow(onDone?: (job: StorageJob) => void) {
    if (busy.value) return
    pageError.value = ''
    busy.value = true
    try {
      const job = await storage.backupNow()
      toast.add({ title: t('lcs.settings.storage.backupStarted', { id: job.id }), color: 'success' })
      onDone?.(job)
      await load()
      return job
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.backupFailed'))
    }
    finally {
      busy.value = false
    }
  }

  async function retryFailed(onDone?: (job: StorageJob) => void) {
    if (busy.value) return
    pageError.value = ''
    busy.value = true
    try {
      const job = await storage.backupRetry()
      toast.add({ title: t('lcs.settings.storage.backupStarted', { id: job.id }), color: 'success' })
      onDone?.(job)
      await load()
      return job
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.retryFailedError'))
    }
    finally {
      busy.value = false
    }
  }

  const historyOpen = ref(false)
  const history = ref<StorageJob[]>([])

  async function loadHistory() {
    try {
      history.value = await storage.backupJobs()
    }
    catch (error) {
      fail(error, t('lcs.common.loadFailed'))
    }
  }

  const migrationOpen = ref(false)
  const migrationTarget = ref<'r2' | 'gdrive'>('r2')
  const migrationDryRun = ref(true)
  const migrationPreview = ref<{ toMigrate: number, files: number, bytes: number, byProvider: Record<string, number>, alreadyOnTarget: number } | null>(null)
  const migrationJob = ref<StorageJob | null>(null)
  const migrationBusy = ref(false)

  async function openMigration() {
    if (pendingAction.value) return
    pageError.value = ''
    migrationPreview.value = null
    migrationJob.value = null
    migrationOpen.value = true
  }

  async function previewMigration(target: 'r2' | 'gdrive') {
    pageError.value = ''
    migrationBusy.value = true
    try {
      migrationPreview.value = await storage.migrationPreview(target)
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.migrationFailed'))
    }
    finally {
      migrationBusy.value = false
    }
  }

  async function startMigration() {
    if (migrationBusy.value) return
    const ok = await confirm({
      kind: 'generic',
      titleKey: 'lcs.settings.storage.migrationConfirmTitle',
      descriptionKey: 'lcs.settings.storage.migrationConfirmHelp',
      confirmColor: 'warning',
    })
    if (!ok) return
    pageError.value = ''
    migrationBusy.value = true
    try {
      migrationJob.value = await storage.migrationStart(migrationTarget.value, migrationDryRun.value)
      toast.add({ title: t('lcs.settings.storage.migrationStarted', { id: migrationJob.value.id }), color: 'success' })
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.migrationFailed'))
    }
    finally {
      migrationBusy.value = false
    }
  }

  const restoreOpen = ref(false)
  const restorePreview = ref<{ restorable: number, replicas: number, primary: string } | null>(null)
  const restoreJob = ref<StorageJob | null>(null)

  async function openRestore() {
    if (pendingAction.value) return
    pageError.value = ''
    restorePreview.value = null
    restoreJob.value = null
    restoreOpen.value = true
    void restoreBusyFetch()
  }

  async function restoreBusyFetch() {
    try {
      restorePreview.value = await storage.restorePreview()
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.restoreFailed'))
    }
  }

  async function executeRestore() {
    if (restorePreview.value && restorePreview.value.restorable === 0) return false
    const ok = await confirm({
      kind: 'generic',
      titleKey: 'lcs.settings.storage.restoreConfirmTitle',
      descriptionKey: 'lcs.settings.storage.restoreConfirmHelp',
      confirmColor: 'warning',
    })
    if (!ok) return false
    pageError.value = ''
    try {
      restoreJob.value = await storage.restore('RESTORE')
      toast.add({ title: t('lcs.settings.storage.restoreStarted', { id: restoreJob.value.id }), color: 'success' })
      await load()
      return true
    }
    catch (error) {
      fail(error, t('lcs.settings.storage.restoreFailed'))
      return false
    }
  }

  return {
    providers, overview, pageError, loading, busy, pendingAction, load,
    testConnection, connectGoogle, disconnectGoogle,
    backupNow, retryFailed, historyOpen, history, loadHistory,
    migrationOpen, migrationTarget, migrationDryRun, migrationPreview, migrationJob, migrationBusy,
    openMigration, previewMigration, startMigration,
    restoreOpen, restorePreview, restoreJob, openRestore, executeRestore,
  }
}
