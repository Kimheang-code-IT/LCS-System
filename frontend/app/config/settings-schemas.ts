import type { DocumentTabSchema } from '~/types/common'
import {
  BACKUP_INTERVAL_OPTIONS,
  CURRENCY_OPTIONS,
  DATE_FORMAT_OPTIONS,
  LANDING_PAGE_OPTIONS,
  LANGUAGE_OPTIONS,
  NUMBER_FORMAT_OPTIONS,
  PAGE_SIZE_OPTIONS,
  TIME_FORMAT_OPTIONS,
  TIMEZONE_OPTIONS,
} from '~/utils/constants/select-options'

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
            options: LANGUAGE_OPTIONS,
          },
          {
            key: 'localization.availableLanguages',
            labelKey: 'lcs.settings.availableLanguages',
            type: 'language-toggles',
            colSpan: 2,
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
          { key: 'telegram.botToken', labelKey: 'lcs.settings.botToken', type: 'secret' },
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
          { key: 'security.accessTokenMinutes', labelKey: 'lcs.settings.accessTokenMinutes', type: 'number' },
          { key: 'security.sessionAbsoluteMinutes', labelKey: 'lcs.settings.sessionAbsoluteMinutes', type: 'number' },
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
        ],
      },
    ],
  },
  {
    id: 'storage',
    labelKey: 'lcs.settings.tabs.storage',
    sections: [
      {
        id: 'storageR2',
        titleKey: 'lcs.settings.storage.r2Section',
        fields: [
          { key: 'storage.providers.r2.accountId', labelKey: 'lcs.settings.storage.r2AccountId', type: 'text', required: true },
          { key: 'storage.providers.r2.bucketName', labelKey: 'lcs.settings.storage.r2BucketName', type: 'text', required: true },
          { key: 'storage.providers.r2.accessKeyId', labelKey: 'lcs.settings.storage.r2AccessKeyId', type: 'text', required: true },
          {
            key: 'storage.providers.r2.secretAccessKey',
            labelKey: 'lcs.settings.storage.r2Secret',
            type: 'secret',
            helpKey: 'lcs.fieldHelp.storageR2Secret',
            colSpan: 2,
          },
          {
            key: 'storage.providers.r2.endpoint',
            labelKey: 'lcs.settings.storage.r2Endpoint',
            type: 'url',
            colSpan: 2,
            helpKey: 'lcs.fieldHelp.storageR2Endpoint',
          },
          { key: 'storage.providers.r2.objectPrefix', labelKey: 'lcs.settings.storage.r2Prefix', type: 'text', colSpan: 2 },
        ],
      },
      {
        id: 'storageGDrive',
        titleKey: 'lcs.settings.storage.gDriveSection',
        fields: [
          {
            key: 'storage.providers.gdrive.authType',
            labelKey: 'lcs.settings.storage.authType',
            type: 'select',
            options: [
              { label: 'Personal Google account (OAuth)', value: 'oauth' },
              { label: 'Google Workspace (service account)', value: 'service_account' },
            ],
          },
          {
            key: 'storage.providers.gdrive.clientId',
            labelKey: 'lcs.settings.storage.clientId',
            type: 'text',
          },
          {
            key: 'storage.providers.gdrive.clientSecret',
            labelKey: 'lcs.settings.storage.clientSecret',
            type: 'secret',
            helpKey: 'lcs.fieldHelp.storageClientSecret',
          },
          {
            key: 'storage.providers.gdrive.serviceAccountJson',
            labelKey: 'lcs.settings.storage.serviceAccountJson',
            type: 'secret',
            helpKey: 'lcs.fieldHelp.storageServiceAccount',
            colSpan: 2,
          },
          {
            key: 'storage.providers.gdrive.rootFolderId',
            labelKey: 'lcs.settings.storage.rootFolderId',
            type: 'text',
            helpKey: 'lcs.fieldHelp.storageRootFolder',
          },
          {
            key: 'storage.providers.gdrive.sharedDriveId',
            labelKey: 'lcs.settings.storage.sharedDriveId',
            type: 'text',
            colSpan: 2,
            helpKey: 'lcs.fieldHelp.storageSharedDrive',
          },
        ],
      },
      {
        id: 'storagePrimary',
        titleKey: 'lcs.settings.storage.primarySection',
        fields: [
          {
            key: 'storage.primaryProvider',
            labelKey: 'lcs.settings.storage.primaryProvider',
            type: 'select',
            options: [
              { label: 'Cloudflare R2', value: 'r2' },
              { label: 'Google Drive', value: 'gdrive' },
            ],
          },
          {
            key: 'storage.backupProvider',
            labelKey: 'lcs.settings.storage.backupProvider',
            type: 'select',
            options: [
              { label: 'Disabled', value: '' },
              { label: 'Cloudflare R2', value: 'r2' },
              { label: 'Google Drive', value: 'gdrive' },
            ],
          },
          { key: 'storage.backupEnabled', labelKey: 'lcs.settings.storage.backupEnabled', type: 'boolean' },
          {
            key: 'storage.backupIntervalHours',
            labelKey: 'lcs.settings.storage.backupSchedule',
            type: 'select',
            options: BACKUP_INTERVAL_OPTIONS,
          },
          { key: 'storage.backupMaxRetries', labelKey: 'lcs.settings.storage.backupRetries', type: 'number' },
          { key: 'storage.retentionDays', labelKey: 'lcs.settings.storage.retentionDays', type: 'number' },
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
  'backup.enabled': 'lcs.fieldHelp.backupEnabled',
  'storage.backupEnabled': 'lcs.fieldHelp.storageBackupEnabled',
  'storage.backupIntervalHours': 'lcs.fieldHelp.storageBackupSchedule',
  'storage.providers.r2.secretAccessKey': 'lcs.fieldHelp.storageR2Secret',
  'storage.providers.r2.endpoint': 'lcs.fieldHelp.storageR2Endpoint',
  'storage.providers.gdrive.clientSecret': 'lcs.fieldHelp.storageClientSecret',
  'storage.providers.gdrive.serviceAccountJson': 'lcs.fieldHelp.storageServiceAccount',
  'storage.providers.gdrive.rootFolderId': 'lcs.fieldHelp.storageRootFolder',
  'storage.providers.gdrive.sharedDriveId': 'lcs.fieldHelp.storageSharedDrive',
  'storage.primaryProvider': 'lcs.fieldHelp.storagePrimary',
  'storage.backupProvider': 'lcs.fieldHelp.storageBackupProvider',
}

/** The former "Storage & Backup" tab's sections, now merged into Backup. */
const STORAGE_SECTIONS = appConfigTabs.find(tab => tab.id === 'storage')?.sections ?? []

/** Administration system settings — Localization, Email, Telegram, Security, Backup (6 tabs). */
export const systemSettingsTabs: DocumentTabSchema[] = appConfigTabs
  .filter(tab => SYSTEM_SETTINGS_TAB_IDS.has(tab.id))
  .map(tab => ({
    ...tab,
    sections: (tab.id === 'backup' ? [...tab.sections, ...STORAGE_SECTIONS] : tab.sections).map(section => ({
      ...section,
      fields: section.fields.map(field => ({
        ...field,
        helpKey: field.helpKey || SETTINGS_FIELD_HELP[field.key],
      })),
    })),
  }))

systemSettingsTabs.push({ id: 'maintenance', labelKey: 'maintenance.settings', sections: [] })

