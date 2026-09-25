import type { DocumentTabSchema } from '~/types/docetra/common'
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
    labelKey: 'docetra.pages.appInfo',
    sections: [
      {
        id: 'info',
        fields: [
          { key: 'applicationName', labelKey: 'docetra.settings.applicationName', type: 'text', required: true, colSpan: 2 },
          { key: 'description', labelKey: 'docetra.fields.description', type: 'textarea', colSpan: 2, rows: 3 },
          { key: 'supportEmail', labelKey: 'docetra.settings.supportEmail', type: 'text' },
          { key: 'supportPhone', labelKey: 'docetra.settings.supportPhone', type: 'text' },
          { key: 'website', labelKey: 'docetra.settings.website', type: 'url' },
          { key: 'address', labelKey: 'docetra.settings.address', type: 'text' },
          { key: 'footer.copyrightText', labelKey: 'docetra.settings.copyright', type: 'text', colSpan: 2 },
          {
            key: 'branding.primaryColor',
            labelKey: 'docetra.settings.primaryColor',
            type: 'color',
          },
          { key: 'branding.mainLogoUrl', labelKey: 'docetra.settings.logo', type: 'image', colSpan: 2 },
        ],
      },
    ],
  },
]

/** App Config tabs. */
export const appConfigTabs: DocumentTabSchema[] = [
  {
    id: 'general',
    labelKey: 'docetra.settings.tabs.general',
    sections: [
      {
        id: 'general',
        titleKey: 'docetra.settings.tabs.general',
        fields: [
          {
            key: 'general.defaultLandingPage',
            labelKey: 'docetra.settings.defaultLandingPage',
            type: 'select',
            options: LANDING_PAGE_OPTIONS,
          },
          {
            key: 'general.defaultPageSize',
            labelKey: 'docetra.settings.defaultPageSize',
            type: 'select',
            options: PAGE_SIZE_OPTIONS,
          },
          {
            key: 'general.defaultRecordView',
            labelKey: 'docetra.settings.defaultRecordView',
            type: 'select',
            options: [
              { label: 'Table', value: 'table' },
              { label: 'Kanban', value: 'kanban' },
            ],
          },
          { key: 'general.maxUploadSizeMb', labelKey: 'docetra.config.maxFileSizeMb', type: 'number' },
          { key: 'general.enableComments', labelKey: 'docetra.config.feature.comments', type: 'boolean' },
          { key: 'general.enableSharing', labelKey: 'docetra.config.feature.sharing', type: 'boolean' },
          { key: 'general.enableExport', labelKey: 'docetra.config.feature.export', type: 'boolean' },
        ],
      },
    ],
  },
  {
    id: 'localization',
    labelKey: 'docetra.settings.tabs.localization',
    sections: [
      {
        id: 'localization',
        titleKey: 'docetra.settings.tabs.localization',
        fields: [
          {
            key: 'localization.defaultLanguage',
            labelKey: 'docetra.settings.defaultLanguage',
            type: 'select',
            options: [
              { label: 'English', value: 'en' },
              { label: 'Khmer', value: 'km' },
            ],
          },
          {
            key: 'localization.timezone',
            labelKey: 'docetra.settings.timezone',
            type: 'select',
            options: TIMEZONE_OPTIONS,
          },
          {
            key: 'localization.dateFormat',
            labelKey: 'docetra.settings.dateFormat',
            type: 'select',
            options: DATE_FORMAT_OPTIONS,
          },
          {
            key: 'localization.timeFormat',
            labelKey: 'docetra.settings.timeFormat',
            type: 'select',
            options: TIME_FORMAT_OPTIONS,
          },
          {
            key: 'localization.numberFormat',
            labelKey: 'docetra.settings.numberFormat',
            type: 'select',
            options: NUMBER_FORMAT_OPTIONS,
          },
          {
            key: 'localization.currency',
            labelKey: 'docetra.settings.currency',
            type: 'select',
            options: CURRENCY_OPTIONS,
          },
        ],
      },
    ],
  },
  {
    id: 'email',
    labelKey: 'docetra.settings.tabs.email',
    sections: [
      {
        id: 'email',
        titleKey: 'docetra.settings.tabs.email',
        fields: [
          { key: 'email.enabled', labelKey: 'docetra.settings.enableEmail', type: 'boolean' },
          { key: 'email.smtpHost', labelKey: 'docetra.settings.smtpHost', type: 'text' },
          { key: 'email.smtpPort', labelKey: 'docetra.settings.smtpPort', type: 'number' },
          { key: 'email.username', labelKey: 'docetra.settings.username', type: 'text' },
          { key: 'email.password', labelKey: 'docetra.settings.password', type: 'secret' },
          {
            key: 'email.encryption',
            labelKey: 'docetra.settings.encryption',
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
    labelKey: 'docetra.settings.tabs.telegram',
    sections: [
      {
        id: 'telegram',
        titleKey: 'docetra.settings.tabs.telegram',
        fields: [
          { key: 'telegram.enabled', labelKey: 'docetra.settings.enableTelegram', type: 'boolean' },
          { key: 'telegram.botDisplayName', labelKey: 'docetra.settings.botDisplayName', type: 'text' },
          { key: 'telegram.botToken', labelKey: 'docetra.settings.botToken', type: 'secret' },
          { key: 'telegram.botUsername', labelKey: 'docetra.settings.botUsername', type: 'text' },
          {
            key: 'telegram.messageLanguage',
            labelKey: 'docetra.settings.messageLanguage',
            type: 'select',
            options: [
              { label: 'English', value: 'en' },
              { label: 'Khmer', value: 'km' },
            ],
          },
          { key: 'telegram.includeOrganization', labelKey: 'docetra.settings.includeOrganization', type: 'boolean' },
          {
            key: 'telegram.destinations',
            labelKey: 'docetra.settings.destinations',
            type: 'telegram-destinations',
            colSpan: 2,
          },
          { key: '__telegramConnection', labelKey: 'docetra.connection.title', type: 'connection-status', colSpan: 2 },
        ],
      },
    ],
  },
  {
    id: 'notifications',
    labelKey: 'docetra.settings.tabs.notifications',
    sections: [
      {
        id: 'notifications',
        titleKey: 'docetra.settings.tabs.notifications',
        fields: [
          { key: 'notifications.inAppEnabled', labelKey: 'docetra.settings.inApp', type: 'boolean' },
          { key: 'notifications.emailEnabled', labelKey: 'docetra.settings.emailChannel', type: 'boolean' },
          { key: 'notifications.telegramEnabled', labelKey: 'docetra.settings.telegramChannel', type: 'boolean' },
          { key: 'notifications.deliveryRetries', labelKey: 'docetra.settings.deliveryRetries', type: 'number' },
          {
            key: 'notifications.rules',
            labelKey: 'docetra.settings.eventRules',
            type: 'notification-rules',
            colSpan: 2,
          },
        ],
      },
    ],
  },
  {
    id: 'security',
    labelKey: 'docetra.settings.tabs.security',
    sections: [
      {
        id: 'security',
        titleKey: 'docetra.settings.tabs.security',
        fields: [
          { key: 'security.sessionTimeoutMinutes', labelKey: 'docetra.settings.sessionTimeout', type: 'number' },
          { key: 'security.maxLoginAttempts', labelKey: 'docetra.settings.maxLoginAttempts', type: 'number' },
          { key: 'security.accountLockMinutes', labelKey: 'docetra.settings.accountLockMinutes', type: 'number' },
          { key: 'security.passwordExpiryDays', labelKey: 'docetra.settings.passwordExpiryDays', type: 'number' },
          { key: 'security.requirePasswordChange', labelKey: 'docetra.settings.requirePasswordChange', type: 'boolean' },
        ],
      },
    ],
  },
  {
    id: 'backup',
    labelKey: 'docetra.settings.tabs.backup',
    sections: [
      {
        id: 'backup',
        titleKey: 'docetra.settings.tabs.backup',
        fields: [
          { key: 'backup.enabled', labelKey: 'docetra.settings.backup.enabled', type: 'boolean' },
          {
            key: 'backup.intervalHours',
            labelKey: 'docetra.settings.backup.intervalHours',
            type: 'select',
            options: BACKUP_INTERVAL_OPTIONS,
          },
          { key: 'backup.spreadsheetId', labelKey: 'docetra.settings.backup.spreadsheetId', type: 'text', colSpan: 2 },
          {
            key: 'backup.serviceAccountJson',
            labelKey: 'docetra.settings.backup.serviceAccountJson',
            type: 'secret',
            colSpan: 2,
          },
          { key: 'backup.worksheetPrefix', labelKey: 'docetra.settings.backup.worksheetPrefix', type: 'text' },
          { key: 'backup.batchSize', labelKey: 'docetra.settings.backup.batchSize', type: 'number' },
          { key: 'backup.excludedTables', labelKey: 'docetra.settings.backup.excludedTables', type: 'csv-list', colSpan: 2 },
        ],
      },
    ],
  },
  {
    id: 'system',
    labelKey: 'docetra.settings.tabs.system',
    sections: [
      {
        id: 'system',
        titleKey: 'docetra.settings.tabs.system',
        fields: [
          { key: 'system.maintenanceMode', labelKey: 'docetra.settings.maintenanceMode', type: 'boolean' },
          { key: 'system.readOnlyMode', labelKey: 'docetra.settings.readOnlyMode', type: 'boolean' },
          {
            key: 'system.paginationDefault',
            labelKey: 'docetra.settings.paginationDefault',
            type: 'select',
            options: PAGE_SIZE_OPTIONS,
          },
          { key: 'system.configurationVersion', labelKey: 'docetra.settings.configurationVersion', type: 'text', readOnly: true },
          { key: 'system.environment', labelKey: 'docetra.settings.environment', type: 'text', readOnly: true },
          { key: 'system.cacheStatus', labelKey: 'docetra.settings.cacheStatus', type: 'text', readOnly: true },
          { key: 'system.backgroundJobStatus', labelKey: 'docetra.settings.jobStatus', type: 'text', readOnly: true },
        ],
      },
    ],
  },
]

const SYSTEM_SETTINGS_TAB_IDS = new Set(['localization', 'email', 'telegram', 'security', 'backup'])
const SETTINGS_FIELD_HELP: Record<string, string> = {
  'email.enabled': 'docetra.fieldHelp.enableEmail',
  'email.replyToEmail': 'docetra.fieldHelp.replyTo',
  'telegram.enabled': 'docetra.fieldHelp.enableTelegram',
  'backup.enabled': 'docetra.fieldHelp.backupEnabled',
  'backup.serviceAccountJson': 'docetra.fieldHelp.backupServiceAccount',
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
  { key: 'name', labelKey: 'docetra.fields.name', type: 'text' as const, required: true },
  { key: 'active', labelKey: 'docetra.status.active', type: 'boolean' as const },
  {
    key: 'accessMode',
    labelKey: 'docetra.settings.accessMode',
    type: 'select' as const,
    options: [
      { label: 'Private', value: 'private' },
      { label: 'Public', value: 'public' },
    ],
  },
  { key: 'maxFileSizeMb', labelKey: 'docetra.config.maxFileSizeMb', type: 'number' as const },
  { key: 'allowedFileTypes', labelKey: 'docetra.config.allowedExtensions', type: 'csv-list' as const, colSpan: 2 as const },
  { key: 'uploadPathPattern', labelKey: 'docetra.settings.uploadPathPattern', type: 'text' as const, colSpan: 2 as const },
]

const storageConnectionField = {
  key: '__storageConnection',
  labelKey: 'docetra.connection.title',
  type: 'connection-status' as const,
  colSpan: 2 as const,
}

/** Storage settings — S3 and Google Drive only. */
export const storageSettingsTabs: DocumentTabSchema[] = [
  {
    id: 'amazon_s3',
    labelKey: 'docetra.settings.storageTabs.amazonS3',
    sections: [
      {
        id: 's3-connection',
        titleKey: 'docetra.settings.connectionSettings',
        fields: [
          {
            key: 'region',
            labelKey: 'docetra.settings.region',
            type: 'select',
            required: true,
            options: AWS_REGION_OPTIONS,
          },
          { key: 'bucket', labelKey: 'docetra.settings.bucket', type: 'text', required: true },
          { key: 'endpoint', labelKey: 'docetra.settings.endpoint', type: 'text', colSpan: 2 },
          { key: 'publicUrl', labelKey: 'docetra.settings.publicUrl', type: 'url', colSpan: 2 },
          { key: 'accessKey', labelKey: 'docetra.settings.accessKey', type: 'text', required: true },
          { key: 'secretKey', labelKey: 'docetra.settings.secretKey', type: 'secret', required: true },
        ],
      },
      {
        id: 's3-options',
        titleKey: 'docetra.settings.tabs.general',
        fields: [...storageCommonFields],
      },
      {
        id: 's3-status',
        titleKey: 'docetra.connection.title',
        fields: [storageConnectionField],
      },
    ],
  },
  {
    id: 'google_drive',
    labelKey: 'docetra.settings.storageTabs.googleDrive',
    sections: [
      {
        id: 'drive-connection',
        titleKey: 'docetra.settings.connectionSettings',
        fields: [
          { key: 'clientId', labelKey: 'docetra.settings.clientId', type: 'text', required: true, colSpan: 2 },
          { key: 'clientSecret', labelKey: 'docetra.settings.clientSecret', type: 'secret', required: true, colSpan: 2 },
          { key: 'folderId', labelKey: 'docetra.settings.folderId', type: 'text', required: true },
          {
            key: 'syncSchedule',
            labelKey: 'docetra.settings.syncSchedule',
            type: 'select',
            options: SYNC_SCHEDULE_OPTIONS,
          },
        ],
      },
      {
        id: 'drive-options',
        titleKey: 'docetra.settings.tabs.general',
        fields: [...storageCommonFields],
      },
      {
        id: 'drive-status',
        titleKey: 'docetra.connection.title',
        fields: [storageConnectionField],
      },
    ],
  },
]
