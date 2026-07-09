import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { useNotificationStore } from '@/stores/notificationStore'

export type DatabaseProvider = 'sqlite' | 'mariadb' | 'mysql' | 'postgresql'

export interface ConnectionInfo {
  host?: string
  port?: number
  database?: string
  [key: string]: unknown
}

export interface ProviderInfo {
  display_name?: string
  available?: boolean
  [key: string]: unknown
}

const PROVIDER_NAMES: Record<DatabaseProvider, string> = {
  sqlite: 'SQLite',
  mariadb: 'MariaDB',
  mysql: 'MySQL',
  postgresql: 'PostgreSQL',
}

const extractDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } } }
  return ax?.response?.data?.detail || fallback
}

export const useDatabaseConfigStore = defineStore('databaseConfig', () => {
  const currentProvider = ref<DatabaseProvider>('sqlite')
  const connectionInfo = ref<ConnectionInfo>({})
  const availableProviders = ref<Record<string, ProviderInfo>>({})
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const providerDisplayName = computed(
    () =>
      PROVIDER_NAMES[currentProvider.value] ||
      String(currentProvider.value).toUpperCase(),
  )

  async function fetchStatus(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response = await axios.get('/api/admin/database/status')
      currentProvider.value = response.data.current_provider as DatabaseProvider
      connectionInfo.value = response.data.connection_info || {}
    } catch (e) {
      error.value = extractDetail(e, 'Failed to fetch database status')
      // eslint-disable-next-line no-console
      console.error('Error fetching database status:', e)
      useNotificationStore().showError(error.value)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchProviders(): Promise<void> {
    try {
      const response = await axios.get('/api/admin/database/providers')
      availableProviders.value = response.data.providers
    } catch (e) {
      error.value = extractDetail(e, 'Failed to fetch database providers')
      // eslint-disable-next-line no-console
      console.error('Error fetching providers:', e)
      useNotificationStore().showError(error.value)
    }
  }

  function clearError(): void {
    error.value = null
  }

  return {
    currentProvider,
    connectionInfo,
    availableProviders,
    isLoading,
    error,
    providerDisplayName,
    fetchStatus,
    fetchProviders,
    clearError,
  }
})
