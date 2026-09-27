import type { AppConfigRepository, AppInfoRepository, BackupRepository } from '~/repositories/contracts/settings'
import type {
  AttachmentRepository,
  AuditRepository,
  ComponentRepository,
  FinanceRepository,
  JobRepository,
  QuotationRepository,
  ReportsRepository,
  ServiceChargeRepository,
  UiSchemaRepository,
} from '~/repositories/contracts/lcs'
import { createHttpAppConfigRepository, createHttpAppInfoRepository, createHttpBackupRepository } from '~/repositories/http/settings'
import { createHttpDynamicTabsRepository } from '~/repositories/http/dynamic-tabs'
import type { DynamicTabsRepository } from '~/repositories/contracts/dynamic-tabs'
import {
  createHttpAttachmentRepository,
  createHttpAuditRepository,
  createHttpComponentRepository,
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

let initialized = false
let appInfoRepo: AppInfoRepository
let appConfigRepo: AppConfigRepository
let backupRepo: BackupRepository
let quotationRepo: QuotationRepository
let jobRepo: JobRepository
let componentRepo: ComponentRepository
let chargeRepo: ServiceChargeRepository
let financeRepo: FinanceRepository
let auditRepo: AuditRepository
let attachmentRepo: AttachmentRepository
let uiSchemaRepo: UiSchemaRepository
let reportsRepo: ReportsRepository
let dynamicTabsRepo: DynamicTabsRepository

function ensureRepositories() {
  if (initialized) return
  initialized = true
  appInfoRepo = createHttpAppInfoRepository()
  appConfigRepo = createHttpAppConfigRepository()
  backupRepo = createHttpBackupRepository()
  quotationRepo = createHttpQuotationRepository()
  jobRepo = createHttpJobRepository()
  componentRepo = createHttpComponentRepository()
  chargeRepo = createHttpServiceChargeRepository()
  financeRepo = createHttpFinanceRepository()
  auditRepo = createHttpAuditRepository()
  attachmentRepo = createHttpAttachmentRepository()
  uiSchemaRepo = createHttpUiSchemaRepository()
  reportsRepo = createHttpReportsRepository()
  dynamicTabsRepo = createHttpDynamicTabsRepository()
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
    components: componentRepo!,
    charges: chargeRepo!,
    finance: financeRepo!,
    audit: auditRepo!,
    attachments: attachmentRepo!,
    uiSchema: uiSchemaRepo!,
    reports: reportsRepo!,
    dynamicTabs: dynamicTabsRepo!,
  }
}

export function useModuleRepository(module: FreightModule): ModuleRepository {
  ensureRepositories()
  return createHttpModuleRepository(module)
}
