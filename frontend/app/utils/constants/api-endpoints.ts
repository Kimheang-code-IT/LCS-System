export const ApiEndpoints = {
  RECORD_TYPES: '/api/v2/configuration/record-types',
  RECORD_ATTRIBUTES: '/api/v2/configuration/record-attributes',

  APP_INFO: '/api/v2/settings/app-info',
  APP_INFO_RESET: '/api/v2/settings/app-info/reset',
  APP_CONFIG: '/api/v2/settings/app-config',
  APP_CONFIG_TEST_EMAIL: '/api/v2/settings/app-config/email/test-connection',
  APP_CONFIG_SEND_TEST_EMAIL: '/api/v2/settings/app-config/email/send-test',
  APP_CONFIG_TEST_TELEGRAM: '/api/v2/settings/app-config/telegram/test-connection',
  APP_CONFIG_SEND_TEST_TELEGRAM: '/api/v2/settings/app-config/telegram/send-test',
  STORAGE_PROVIDERS: '/api/v2/settings/storage',
  STORAGE_PROVIDER: (id: string) => `/api/v2/settings/storage/${id}`,
  STORAGE_PROVIDER_TEST: (id: string) => `/api/v2/settings/storage/${id}/test-connection`,
  STORAGE_PROVIDER_SET_DEFAULT: (id: string) => `/api/v2/settings/storage/${id}/set-default`,
  STORAGE_PROVIDER_SET_ACTIVE: (id: string) => `/api/v2/settings/storage/${id}/set-active`,

  SEARCH: '/api/v2/search',
  SEARCH_ASK: '/api/v2/search/ask',
} as const
