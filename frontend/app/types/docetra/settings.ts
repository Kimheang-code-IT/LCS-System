export type ConnectionStatus =
  | 'not_tested'
  | 'testing'
  | 'connected'
  | 'failed'
  | 'disabled'

export type StorageProviderType =
  | 'local'
  | 'cloudflare_r2'
  | 'amazon_s3'
  | 'minio'
  | 'google_drive'

export type EncryptionType = 'none' | 'ssl' | 'tls' | 'starttls'

export type TelegramConnectionMode = 'bot_api' | 'webhook'

export type TelegramDestinationType = 'chat' | 'channel' | 'group' | 'organization'

export type NotificationChannel = 'in_app' | 'email' | 'telegram'

export type NotificationEvent =
  | 'record_created'
  | 'record_assigned'
  | 'stage_changed'
  | 'deadline_approaching'
  | 'record_overdue'
  | 'meeting_created'
  | 'file_uploaded'

export type AppFontSize = 'sm' | 'md' | 'lg' | 'xl'

export interface AppBranding {
  mainLogoUrl?: string
  sidebarLogoUrl?: string
  faviconUrl?: string
  loginBackgroundUrl?: string
  /** System primary color (hex, e.g. #e8472a). */
  primaryColor: string
  secondaryColor: string
  /** @deprecated Per-user preference — use preferences store / user menu. */
  fontSize?: AppFontSize
}

export interface AppFooterInfo {
  copyrightText: string
  privacyPolicyUrl?: string
  termsUrl?: string
}

export interface AppInfo {
  applicationName: string
  shortName: string
  organizationName: string
  description?: string
  supportEmail?: string
  supportPhone?: string
  website?: string
  address?: string
  branding: AppBranding
  footer: AppFooterInfo
  updatedAt: string
}

export interface EmailConfig {
  enabled: boolean
  smtpHost: string
  smtpPort: number
  username: string
  /** Masked in UI; never log plaintext. */
  password: string
  encryption: EncryptionType
  fromName: string
  fromEmail: string
  replyToEmail?: string
  timeoutSeconds: number
  connectionStatus: ConnectionStatus
  lastTestedAt?: string
  lastTestMessage?: string
}

export interface TelegramDestination {
  id: string
  name: string
  type: TelegramDestinationType
  chatId: string
  organizationId?: string
  organizationName?: string
  recordTypeId?: string
  recordTypeName?: string
  enabledEvents: NotificationEvent[]
  status: ConnectionStatus
  enabled: boolean
}

export interface TelegramConfig {
  enabled: boolean
  botDisplayName: string
  botToken: string
  botUsername?: string
  connectionMode: TelegramConnectionMode
  defaultDestinationId?: string
  messageLanguage: 'en' | 'km'
  includeRecordLink: boolean
  includeOrganization: boolean
  includeAssignedOfficer: boolean
  connectionStatus: ConnectionStatus
  lastTestedAt?: string
  lastTestMessage?: string
  destinations: TelegramDestination[]
  messageTemplate: string
}

export interface NotificationRule {
  id: string
  event: NotificationEvent
  channels: NotificationChannel[]
  enabled: boolean
}

export interface AppConfigGeneral {
  defaultLandingPage: string
  defaultPageSize: number
  defaultRecordView: 'table' | 'kanban'
  enableComments: boolean
  enableSharing: boolean
  enableExport: boolean
  maxUploadSizeMb: number
}

export interface AppConfigLocalization {
  defaultLanguage: 'en' | 'km'
  availableLanguages: Array<'en' | 'km'>
  timezone: string
  dateFormat: string
  timeFormat: string
  firstDayOfWeek: 0 | 1 | 6
  numberFormat: string
  currency: string
  locale: string
}

export interface AppConfigNotifications {
  inAppEnabled: boolean
  emailEnabled: boolean
  telegramEnabled: boolean
  deliveryRetries: number
  quietHoursEnabled: boolean
  quietHoursStart?: string
  quietHoursEnd?: string
  language: 'en' | 'km'
  rules: NotificationRule[]
}

export interface AppConfigSecurity {
  sessionTimeoutMinutes: number
  maxLoginAttempts: number
  accountLockMinutes: number
  passwordExpiryDays: number
  requirePasswordChange: boolean
  allowedUploadExtensions: string[]
  auditRetentionDays: number
  /** UI disclaimer: not enforced without backend. */
  frontendOnly: true
}

export interface AppConfigSystem {
  maintenanceMode: boolean
  readOnlyMode: boolean
  paginationDefault: number
  configurationVersion: string
  environment: 'development' | 'staging' | 'production'
  cacheStatus: 'healthy' | 'degraded' | 'unknown'
  backgroundJobStatus: 'idle' | 'running' | 'failed' | 'unknown'
}

export interface AppConfig {
  general: AppConfigGeneral
  localization: AppConfigLocalization
  email: EmailConfig
  telegram: TelegramConfig
  notifications: AppConfigNotifications
  security: AppConfigSecurity
  system: AppConfigSystem
  updatedAt: string
}

export interface StorageProvider {
  id: string
  name: string
  type: StorageProviderType
  active: boolean
  isDefault: boolean
  maxFileSizeMb: number
  allowedFileTypes: string[]
  accessMode: 'public' | 'private'
  uploadPathPattern: string
  connectionStatus: ConnectionStatus
  lastTestedAt?: string
  lastTestMessage?: string
  /** S3-compatible */
  endpoint?: string
  region?: string
  bucket?: string
  accessKey?: string
  secretKey?: string
  publicUrl?: string
  pathStyle?: boolean
  /** Google Drive */
  folderId?: string
  clientId?: string
  clientSecret?: string
  credentialStatus?: ConnectionStatus
  syncStatus?: ConnectionStatus
  syncSchedule?: string
  updatedAt: string
}

export type CreateStorageProviderInput = Omit<
  StorageProvider,
  'id' | 'updatedAt' | 'connectionStatus' | 'isDefault'
> & { isDefault?: boolean }

export type UpdateStorageProviderInput = Partial<CreateStorageProviderInput>

export const NOTIFICATION_EVENTS: NotificationEvent[] = [
  'record_created',
  'record_assigned',
  'stage_changed',
  'deadline_approaching',
  'record_overdue',
  'meeting_created',
  'file_uploaded',
]

export const TELEGRAM_TEMPLATE_VARIABLES = [
  '{{record_number}}',
  '{{record_title}}',
  '{{record_type}}',
  '{{status}}',
  '{{stage}}',
  '{{organization_name}}',
  '{{assigned_officer}}',
  '{{due_at}}',
  '{{created_by}}',
  '{{record_url}}',
] as const

export const DEFAULT_TELEGRAM_TEMPLATE = [
  '[{{record_type}}] {{record_number}}',
  '{{record_title}}',
  'Status: {{status}} · Stage: {{stage}}',
  'Org: {{organization_name}} · Assignee: {{assigned_officer}}',
  '{{record_url}}',
].join('\n')
