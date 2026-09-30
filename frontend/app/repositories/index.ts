import type { AppConfigRepository, AppInfoRepository, BackupRepository } from '~/repositories/contracts/settings'
import type {
  AttachmentRepository,
  AuditRepository,
  FinanceRepository,
  JobRepository,
  QuotationRepository,
  ReportsRepository,
  ServiceChargeRepository,
  UiSchemaRepository,
} from '~/repositories/contracts/lcs'
import { createHttpAppConfigRepository, createHttpAppInfoRepository, createHttpBackupRepository } from '~/repositories/http/settings'
import { createHttpComponentConfigRepository } from '~/repositories/http/component-config'
import type { ComponentConfigRepository } from '~/repositories/contracts/component-config'
import {
  createHttpAttachmentRepository,
  createHttpAuditRepository,
  createHttpFinanceRepository,
  createHttpJobRepository,
  createHttpQuotationRepository,
  createHttpReportsRepository,
  createHttpServiceChargeRepository,
  createHttpUiSchemaRepository,
} from '~/repositories/http/lcs'
import { createHttpModuleRepository } from '~/repositories/http/module'
import type { FreightModule } from '~/config/freight-modules'
import type { ModuleRepository } from '~/repositories/contracts/module'
import type { ArchiveRepository } from '~/repositories/contracts/archive'
import { createHttpArchiveRepository } from '~/repositories/http/archive'

let initialized = false
let appInfoRepo: AppInfoRepository
let appConfigRepo: AppConfigRepository
let backupRepo: BackupRepository
let quotationRepo: QuotationRepository
let jobRepo: JobRepository
let componentConfigRepo: ComponentConfigRepository
let chargeRepo: ServiceChargeRepository
let financeRepo: FinanceRepository
let auditRepo: AuditRepository
let attachmentRepo: AttachmentRepository
let uiSchemaRepo: UiSchemaRepository
let reportsRepo: ReportsRepository
let archiveRepo: ArchiveRepository

function ensureRepositories() {
  if (initialized) return
  initialized = true
  appInfoRepo = createHttpAppInfoRepository()
  appConfigRepo = createHttpAppConfigRepository()
  backupRepo = createHttpBackupRepository()
  quotationRepo = createHttpQuotationRepository()
  jobRepo = createHttpJobRepository()
  componentConfigRepo = createHttpComponentConfigRepository()
  chargeRepo = createHttpServiceChargeRepository()
  financeRepo = createHttpFinanceRepository()
  auditRepo = createHttpAuditRepository()
  attachmentRepo = createHttpAttachmentRepository()
  uiSchemaRepo = createHttpUiSchemaRepository()
  reportsRepo = createHttpReportsRepository()
  archiveRepo = createHttpArchiveRepository()
}

export function useArchiveRepository(): ArchiveRepository {
  ensureRepositories()
  return archiveRepo!
}

export function useSettingsRepositories() {
  ensureRepositories()
  return { appInfo: appInfoRepo!, appConfig: appConfigRepo!, backup: backupRepo! }
}

export function useLcsRepositories() {
  ensureRepositories()
  return {
    quotations: quotationRepo!,
    jobs: jobRepo!,
    componentConfig: componentConfigRepo!,
    charges: chargeRepo!,
    finance: financeRepo!,
    audit: auditRepo!,
    attachments: attachmentRepo!,
    uiSchema: uiSchemaRepo!,
    reports: reportsRepo!,
  }
}

export function useModuleRepository(module: FreightModule): ModuleRepository {
  ensureRepositories()
  return createHttpModuleRepository(module)
}
