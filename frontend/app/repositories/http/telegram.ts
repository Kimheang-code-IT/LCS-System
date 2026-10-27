import { ApiEndpoints } from '~/utils/constants/api-endpoints'
import { unwrapApiData } from './response'
import type { TelegramDeliveryHistory, TelegramPairing } from '~/types/settings'

export function createHttpTelegramRepository() {
  const api = useApi()
  return {
    history: async (params: Record<string, string | number> = {}) => unwrapApiData(await api.get<TelegramDeliveryHistory>(`${ApiEndpoints.TELEGRAM_HISTORY}?${new URLSearchParams(Object.entries(params).filter(([, value]) => value !== '').map(([key, value]) => [key, String(value)]))}`)),
    retry: async (id: number) => unwrapApiData(await api.post(ApiEndpoints.TELEGRAM_HISTORY_RETRY(id), {})),
    registerWebhook: async () => unwrapApiData(await api.post<{ status: string }>(ApiEndpoints.TELEGRAM_WEBHOOK_SETUP, {})),
    pairGroup: async () => unwrapApiData(await api.post<TelegramPairing>(ApiEndpoints.TELEGRAM_GROUP_PAIR, {})),
    candidate: async () => unwrapApiData(await api.get<{ name: string | null, verified: boolean }>(ApiEndpoints.TELEGRAM_GROUP_CANDIDATE)),
    confirmGroup: async (challenge: string) => unwrapApiData(await api.post(ApiEndpoints.TELEGRAM_GROUP_CONFIRM, { challenge })),
    disconnectGroup: async () => unwrapApiData(await api.delete(ApiEndpoints.TELEGRAM_GROUP)),
    myLink: async () => unwrapApiData(await api.get<{ connected: boolean, displayName: string | null, verifiedAt: string | null, blocked: boolean }>(ApiEndpoints.TELEGRAM_MY_LINK)),
    pairPrivate: async (currentPassword: string) => unwrapApiData(await api.post<TelegramPairing>(ApiEndpoints.TELEGRAM_MY_PAIR, { current_password: currentPassword })),
    disconnectPrivate: async (currentPassword: string) => unwrapApiData(await api.post(ApiEndpoints.TELEGRAM_MY_DISCONNECT, { current_password: currentPassword })),
  }
}
