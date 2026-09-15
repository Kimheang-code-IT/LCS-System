export const ApiEndpoints = {
  APP_INFO: '/api/v1/settings/app-info',
  APP_INFO_RESET: '/api/v1/settings/app-info/reset',
  APP_CONFIG: '/api/v1/settings/app-config',
  APP_CONFIG_TEST_EMAIL: '/api/v1/settings/app-config/email/test-connection',
  APP_CONFIG_SEND_TEST_EMAIL: '/api/v1/settings/app-config/email/send-test',
  APP_CONFIG_TEST_TELEGRAM: '/api/v1/settings/app-config/telegram/test-connection',
  APP_CONFIG_SEND_TEST_TELEGRAM: '/api/v1/settings/app-config/telegram/send-test',

  SEARCH: '/api/v1/search',
  SEARCH_ASK: '/api/v1/search/ask',
} as const
