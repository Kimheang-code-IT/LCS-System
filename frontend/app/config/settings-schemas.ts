import type { DocumentTabSchema } from '~/types/common'
import {
  AWS_REGION_OPTIONS,
  BACKUP_INTERVAL_OPTIONS,
  CURRENCY_OPTIONS,
  DATE_FORMAT_OPTIONS,
  LANDING_PAGE_OPTIONS,
  NUMBER_FORMAT_OPTIONS,
  PAGE_SIZE_OPTIONS,
  SYNC_SCHEDULE_OPTIONS,
  TIME_FORMAT_OPTIONS,
  TIMEZONE_OPTIONS,
} from '~/utils/constants/select-options'

/** App Info — flat form (no tabs UI when single tab). */
export const appInfoTabs: DocumentTabSchema[] = [
  {
    id: 'info',
    labelKey: 'lcs.pages.appInfo',
    sections: [
      {
        id: 'info',
        fields: [
          { key: 'applicationName', labelKey: 'lcs.settings.applicationName', type: 'text', required: true, colSpan: 2 },
          { key: 'description', labelKey: 'lcs.fields.description', type: 'textarea', colSpan: 2, rows: 3 },
          { key: 'supportEmail', labelKey: 'lcs.settings.supportEmail', type: 'text' },
          { key: 'supportPhone', labelKey: 'lcs.settings.supportPhone', type: 'text' },
          { key: 'website', labelKey: 'lcs.settings.website', type: 'url' },
          { key: 'address', labelKey: 'lcs.settings.address', type: 'text' },
          { key: 'footer.copyrightText', labelKey: 'lcs.settings.copyright', type: 'text', colSpan: 2 },
          {
            key: 'branding.primaryColor',
            labelKey: 'lcs.settings.primaryColor',
            type: 'color',
          },
          { key: 'branding.mainLogoUrl', labelKey: 'lcs.settings.logo', type: 'image', colSpan: 2 },
        ],
      },
    ],
  },
]

/** App Config tabs. */
export const appConfigTabs: DocumentTabSchema[] = [
  {
    id: 'general',
    labelKey: 'lcs.settings.tabs.general',
    sections: [
      {
        id: 'general',
        titleKey: 'lcs.settings.tabs.general',
        fields: [
          {
            key: 'general.defaultLandingPage',
            labelKey: 'lcs.settings.defaultLandingPage',
            type: 'select',
            options: LANDING_PAGE_OPTIONS,
          },
          {
            key: 'general.defaultPageSize',
            labelKey: 'lcs.settings.defaultPageSize',
            type: 'select',
            options: PAGE_SIZE_OPTIONS,
          },
          {
            key: 'general.defaultRecordView',
            labelKey: 'lcs.settings.defaultRecordView',
            type: 'select',
            options: [
              { label: 'Table', value: 'table' },
              { label: 'Kanban', value: 'kanban' },
            ],
          },
          { key: 'general.maxUploadSizeMb', labelKey: 'lcs.config.maxFileSizeMb', type: 'number' },
          { key: 'general.enableComments', labelKey: 'lcs.config.feature.comments', type: 'boolean' },
          { key: 'general.enableSharing', labelKey: 'lcs.config.feature.sharing', type: 'boolean' },
          { key: 'general.enableExport', labelKey: 'lcs.config.feature.export', type: 'boolean' },
        ],
      },
    ],
  },
  {
    id: 'localization',
    labelKey: 'lcs.settings.tabs.localization',
    sections: [
      {
        id: 'localization',
        titleKey: 'lcs.settings.tabs.localization',
        fields: [
          {
            key: 'localization.defaultLanguage',
            labelKey: 'lcs.settings.defaultLanguage',
            type: 'select',
            options: [
              { label: 'English', value: 'en' },
              { label: 'Khmer', value: 'km' },
            ],
          },
          {
            key: 'localization.timezone',
            labelKey: 'lcs.settings.timezone',
            type: 'select',
            options: TIMEZONE_OPTIONS,
          },
          {
            key: 'localization.dateFormat',
            labelKey: 'lcs.settings.dateFormat',
            type: 'select',
            options: DATE_FORMAT_OPTIONS,
          },
          {
            key: 'localization.timeFormat',
            labelKey: 'lcs.settings.timeFormat',
            type: 'select',
            options: TIME_FORMAT_OPTIONS,
          },
          {
            key: 'localization.numberFormat',
            labelKey: 'lcs.settings.numberFormat',
            type: 'select',
            options: NUMBER_FORMAT_OPTIONS,
          },
          {
            key: 'localization.currency',
            labelKey: 'lcs.settings.currency',
            type: 'select',
            options: CURRENCY_OPTIONS,
          },
        ],
      },
    ],
  },
  {
    id: 'email',
    labelKey: 'lcs.settings.tabs.email',
    sections: [
      {
        id: 'email',
        titleKey: 'lcs.settings.tabs.email',
        fields: [
          { key: 'email.enabled', labelKey: 'lcs.settings.enableEmail', type: 'boolean' },
          { key: 'email.smtpHost', labelKey: 'lcs.settings.smtpHost', type: 'text' },
          { key: 'email.smtpPort', labelKey: 'lcs.settings.smtpPort', type: 'number' },
          { key: 'email.username', labelKey: 'lcs.settings.username', type: 'text' },
          { key: 'email.password', labelKey: 'lcs.settings.password', type: 'secret' },
          {
            key: 'email.encryption',
            labelKey: 'lcs.settings.encryption',
            type: 'select',
            options: [
              { label: 'None', value: 'none' },
              { label: 'SSL', value: 'ssl' },
              { label: 'TLS', value: 'tls' },
              { label: 'STARTTLS', value: 'starttls' },
            ],
          },
        ],
      },
    ],
  },
  {
    id: 'telegram',
    labelKey: 'lcs.settings.tabs.telegram',
    sections: [
      {
        id: 'telegram',
        titleKey: 'lcs.settings.tabs.telegram',
        fields: [
          { key: 'telegram.enabled', labelKey: 'lcs.settings.enableTelegram', type: 'boolean' },
          { key: 'telegram.botDisplayName', labelKey: 'lcs.settings.botDisplayName', type: 'text' },
          { key: 'telegram.botToken', labelKey: 'lcs.settings.botToken', type: 'secret' },
          { key: 'telegram.botUsername', labelKey: 'lcs.settings.botUsername', type: 'text' },
          {
            key: 'telegram.messageLanguage',
            labelKey: 'lcs.settings.messageLanguage',
            type: 'select',
            options: [
              { label: 'English', value: 'en' },
              { label: 'Khmer', value: 'km' },
            ],
          },
          { key: 'telegram.includeOrganization', labelKey: 'lcs.settings.includeOrganization', type: 'boolean' },
          {
            key: 'telegram.destinations',
            labelKey: 'lcs.settings.destinations',
            type: 'telegram-destinations',
            colSpan: 2,
          },
          { key: '__telegramConnection', labelKey: 'lcs.connection.title', type: 'connection-status', colSpan: 2 },
        ],
      },
    ],
  },
  {
    id: 'notifications',
    labelKey: 'lcs.settings.tabs.notifications',
    sections: [
      {
        id: 'notifications',
        titleKey: 'lcs.settings.tabs.notifications',
        fields: [
          { key: 'notifications.inAppEnabled', labelKey: 'lcs.settings.inApp', type: 'boolean' },
          { key: 'notifications.emailEnabled', labelKey: 'lcs.settings.emailChannel', type: 'boolean' },
          { key: 'notifications.telegramEnabled', labelKey: 'lcs.settings.telegramChannel', type: 'boolean' },
          { key: 'notifications.deliveryRetries', labelKey: 'lcs.settings.deliveryRetries', type: 'number' },
          {
            key: 'notifications.rules',
            labelKey: 'lcs.settings.eventRules',
            type: 'notification-rules',
            colSpan: 2,
          },
        ],
      },
    ],
  },
  {
    id: 'security',
    labelKey: 'lcs.settings.tabs.security',
    sections: [
      {
        id: 'security',
        titleKey: 'lcs.settings.tabs.security',
        fields: [
          { key: 'security.sessionTimeoutMinutes', labelKey: 'lcs.settings.sessionTimeout', type: 'number' },
          { key: 'security.maxLoginAttempts', labelKey: 'lcs.settings.maxLoginAttempts', type: 'number' },
          { key: 'security.accountLockMinutes', labelKey: 'lcs.settings.accountLockMinutes', type: 'number' },
          { key: 'security.passwordExpiryDays', labelKey: 'lcs.settings.passwordExpiryDays', type: 'number' },
          { key: 'security.requirePasswordChange', labelKey: 'lcs.settings.requirePasswordChange', type: 'boolean' },
        ],
      },
    ],
  },
  {
    id: 'backup',
    labelKey: 'lcs.settings.tabs.backup',
    sections: [
      {
        id: 'backup',
        titleKey: 'lcs.settings.tabs.backup',
        fields: [
          { key: 'backup.enabled', labelKey: 'lcs.settings.backup.enabled', type: 'boolean' },
          {
            key: 'backup.intervalHours',
            labelKey: 'lcs.settings.backup.intervalHours',
            type: 'select',
            options: BACKUP_INTERVAL_OPTIONS,
          },
          { key: 'backup.r2AccountId', labelKey: 'lcs.settings.backup.r2AccountId', type: 'text', required: true },
          { key: 'backup.r2AccessKeyId', labelKey: 'lcs.settings.backup.r2AccessKeyId', type: 'text', required: true },
          {
            key: 'backup.r2SecretAccessKey',
            labelKey: 'lcs.settings.backup.r2SecretAccessKey',
            type: 'secret',
            required: true,
          },
          { key: 'backup.r2BucketName', labelKey: 'lcs.settings.backup.r2BucketName', type: 'text', required: true },
          {
            key: 'backup.r2Endpoint',
            labelKey: 'lcs.settings.backup.r2Endpoint',
            type: 'url',
            required: true,
            colSpan: 2,
          },
          { key: 'backup.r2Prefix', labelKey: 'lcs.settings.backup.r2Prefix', type: 'text', colSpan: 2 },
        ],
      },
      {
        id: 'backup-google-sheets',
        titleKey: 'lcs.settings.backup.googleSheetsLegacy',
        fields: [
          { key: 'backup.spreadsheetId', labelKey: 'lcs.settings.backup.spreadsheetId', type: 'text', colSpan: 2 },
          {
            key: 'backup.serviceAccountJson',
            labelKey: 'lcs.settings.backup.serviceAccountJson',
            type: 'secret',
            colSpan: 2,
          },
        ],
      },
    ],
  },
  {
    id: 'system',
    labelKey: 'lcs.settings.tabs.system',
    sections: [
      {
        id: 'system',
        titleKey: 'lcs.settings.tabs.system',
        fields: [
          { key: 'system.maintenanceMode', labelKey: 'lcs.settings.maintenanceMode', type: 'boolean' },
          { key: 'system.readOnlyMode', labelKey: 'lcs.settings.readOnlyMode', type: 'boolean' },
          {
            key: 'system.paginationDefault',
            labelKey: 'lcs.settings.paginationDefault',
            type: 'select',
            options: PAGE_SIZE_OPTIONS,
          },
          { key: 'system.configurationVersion', labelKey: 'lcs.settings.configurationVersion', type: 'text', readOnly: true },
          { key: 'system.environment', labelKey: 'lcs.settings.environment', type: 'text', readOnly: true },
          { key: 'system.cacheStatus', labelKey: 'lcs.settings.cacheStatus', type: 'text', readOnly: true },
          { key: 'system.backgroundJobStatus', labelKey: 'lcs.settings.jobStatus', type: 'text', readOnly: true },
        ],
      },
    ],
  },
]

const SYSTEM_SETTINGS_TAB_IDS = new Set(['localization', 'email', 'telegram', 'security', 'backup'])
const SETTINGS_FIELD_HELP: Record<string, string> = {
  'email.enabled': 'lcs.fieldHelp.enableEmail',
  'email.replyToEmail': 'lcs.fieldHelp.replyTo',
  'telegram.enabled': 'lcs.fieldHelp.enableTelegram',
  'backup.enabled': 'lcs.fieldHelp.backupEnabled',
  'backup.r2SecretAccessKey': 'lcs.fieldHelp.backupR2Secret',
  'backup.r2Prefix': 'lcs.fieldHelp.backupR2Prefix',
  'backup.serviceAccountJson': 'lcs.fieldHelp.backupServiceAccount',
}

/** Administration system settings — Localization, Email, Telegram, Security, Backup. */
export const systemSettingsTabs: DocumentTabSchema[] = appConfigTabs
  .filter(tab => SYSTEM_SETTINGS_TAB_IDS.has(tab.id))
  .map(tab => ({
    ...tab,
    sections: tab.sections.map(section => ({
      ...section,
      fields: section.fields.map(field => ({
        ...field,
        helpKey: field.helpKey || SETTINGS_FIELD_HELP[field.key],
      })),
    })),
  }))

const storageCommonFields = [
  { key: 'name', labelKey: 'lcs.fields.name', type: 'text' as const, required: true },
  { key: 'active', labelKey: 'lcs.status.active', type: 'boolean' as const },
  {
    key: 'accessMode',
    labelKey: 'lcs.settings.accessMode',
    type: 'select' as const,
    options: [
      { label: 'Private', value: 'private' },
      { label: 'Public', value: 'public' },
    ],
  },
  { key: 'maxFileSizeMb', labelKey: 'lcs.config.maxFileSizeMb', type: 'number' as const },
  { key: 'allowedFileTypes', labelKey: 'lcs.config.allowedExtensions', type: 'csv-list' as const, colSpan: 2 as const },
  { key: 'uploadPathPattern', labelKey: 'lcs.settings.uploadPathPattern', type: 'text' as const, colSpan: 2 as const },
]

const storageConnectionField = {
  key: '__storageConnection',
  labelKey: 'lcs.connection.title',
  type: 'connection-status' as const,
  colSpan: 2 as const,
}

/** Storage settings — S3 and Google Drive only. */
export const storageSettingsTabs: DocumentTabSchema[] = [
  {
    id: 'amazon_s3',
    labelKey: 'lcs.settings.storageTabs.amazonS3',
    sections: [
      {
        id: 's3-connection',
        titleKey: 'lcs.settings.connectionSettings',
        fields: [
          {
            key: 'region',
            labelKey: 'lcs.settings.region',
            type: 'select',
            required: true,
            options: AWS_REGION_OPTIONS,
          },
          { key: 'bucket', labelKey: 'lcs.settings.bucket', type: 'text', required: true },
          { key: 'endpoint', labelKey: 'lcs.settings.endpoint', type: 'text', colSpan: 2 },
          { key: 'publicUrl', labelKey: 'lcs.settings.publicUrl', type: 'url', colSpan: 2 },
          { key: 'accessKey', labelKey: 'lcs.settings.accessKey', type: 'text', required: true },
          { key: 'secretKey', labelKey: 'lcs.settings.secretKey', type: 'secret', required: true },
        ],
      },
      {
        id: 's3-options',
        titleKey: 'lcs.settings.tabs.general',
        fields: [...storageCommonFields],
      },
      {
        id: 's3-status',
        titleKey: 'lcs.connection.title',
        fields: [storageConnectionField],
      },
    ],
  },
  {
    id: 'google_drive',
    labelKey: 'lcs.settings.storageTabs.googleDrive',
    sections: [
      {
        id: 'drive-connection',
        titleKey: 'lcs.settings.connectionSettings',
        fields: [
          { key: 'clientId', labelKey: 'lcs.settings.clientId', type: 'text', required: true, colSpan: 2 },
          { key: 'clientSecret', labelKey: 'lcs.settings.clientSecret', type: 'secret', required: true, colSpan: 2 },
          { key: 'folderId', labelKey: 'lcs.settings.folderId', type: 'text', required: true },
          {
            key: 'syncSchedule',
            labelKey: 'lcs.settings.syncSchedule',
            type: 'select',
            options: SYNC_SCHEDULE_OPTIONS,
          },
        ],
      },
      {
        id: 'drive-options',
        titleKey: 'lcs.settings.tabs.general',
        fields: [...storageCommonFields],
      },
      {
        id: 'drive-status',
        titleKey: 'lcs.connection.title',
        fields: [storageConnectionField],
      },
    ],
  },
]
