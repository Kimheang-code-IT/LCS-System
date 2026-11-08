import { TelegramEndpoints } from './api-v1-endpoints'

export const ApiEndpoints = {
  ...TelegramEndpoints,
  APP_INFO: '/api/v1/settings/app-info',
  APP_INFO_RESET: '/api/v1/settings/app-info/reset',
  APP_CONFIG: '/api/v1/settings/app-config',
  APP_CONFIG_TEST_EMAIL: '/api/v1/settings/app-config/email/test-connection',
  APP_CONFIG_SEND_TEST_EMAIL: '/api/v1/settings/app-config/email/send-test',
  APP_CONFIG_TEST_TELEGRAM: '/api/v1/settings/app-config/telegram/test-connection',
  APP_CONFIG_SEND_TEST_TELEGRAM: '/api/v1/settings/app-config/telegram/send-test',
  APP_CONFIG_TEST_TELEGRAM_CLIENT: '/api/v1/settings/app-config/telegram/client/test-connection',
  APP_CONFIG_SEND_TEST_TELEGRAM_CLIENT: '/api/v1/settings/app-config/telegram/client/send-test',
  SETTINGS_RESET_DATA: '/api/v1/settings/reset-data',

  BACKUP_STATUS: '/api/v1/backup/status',
  BACKUP_RUNS: '/api/v1/backup/runs',
  BACKUP_RUN: '/api/v1/backup/run',
  BACKUP_RESTORE: '/api/v1/backup/restore',
  BACKUP_TEST_CONNECTION: '/api/v1/backup/test-connection',

  STORAGE_STATUS: '/api/v1/settings/storage/status',
  STORAGE_TEST_CONNECTION: '/api/v1/settings/storage/test-connection',
  STORAGE_GOOGLE_AUTHORIZE: '/api/v1/settings/storage/google/authorize',
  STORAGE_GOOGLE_DISCONNECT: '/api/v1/settings/storage/google/disconnect',
  STORAGE_BACKUP_NOW: '/api/v1/settings/storage/backup-now',
  STORAGE_BACKUP_JOBS: '/api/v1/settings/storage/backup/jobs',
  STORAGE_BACKUP_RETRY: '/api/v1/settings/storage/backup/retry',
  STORAGE_PRIMARY: '/api/v1/settings/storage/primary',
  STORAGE_MIGRATION_PREVIEW: '/api/v1/settings/storage/migration/preview',
  STORAGE_MIGRATION_START: '/api/v1/settings/storage/migration/start',
  STORAGE_MIGRATION_CLEANUP: '/api/v1/settings/storage/migration/cleanup',
  STORAGE_PROGRESS: '/api/v1/settings/storage/progress',
  STORAGE_RESTORE_PREVIEW: '/api/v1/settings/storage/restore/preview',
  STORAGE_RESTORE: '/api/v1/settings/storage/restore',

  SEARCH: '/api/v1/search',
  SEARCH_ASK: '/api/v1/search/ask',
} as const
