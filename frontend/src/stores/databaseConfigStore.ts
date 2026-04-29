import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { useNotificationStore } from '@/stores/notificationStore'

export type DatabaseProvider = 'sqlite' | 'mariadb' | 'mysql' | 'postgresql'
export type MigrationStatusValue = 'in_progress' | 'completed' | 'failed' | 'idle'

export interface MigrationStatus {
  status: MigrationStatusValue
  tables_migrated?: number
  total_tables?: number
  current_table?: string
  error_message?: string
  [key: string]: unknown
}

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

export interface ConnectionTestResult {
  success: boolean
  message?: string
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
  const migrationStatus = ref<MigrationStatus | null>(null)
  const connectionInfo = ref<ConnectionInfo>({})
  const availableProviders = ref<Record<string, ProviderInfo>>({})
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const pollingInterval = ref<ReturnType<typeof setInterval> | null>(null)
  const connectionTestResult = ref<ConnectionTestResult | null>(null)

  const canMigrate = computed(() => currentProvider.value === 'sqlite')
  const isMigrating = computed(() => migrationStatus.value?.status === 'in_progress')
  const migrationCompleted = computed(() => migrationStatus.value?.status === 'completed')
  const migrationFailed = computed(() => migrationStatus.value?.status === 'failed')

  const migrationProgress = computed(() => {
    if (!migrationStatus.value) return 0
    const { tables_migrated = 0, total_tables = 0 } = migrationStatus.value
    return total_tables > 0 ? Math.round((tables_migrated / total_tables) * 100) : 0
  })

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

  async function testConnection(targetUrl: string): Promise<ConnectionTestResult> {
    isLoading.value = true
    connectionTestResult.value = null

    try {
      const response = await axios.post('/api/admin/database/test-connection', {
        target_url: targetUrl,
      })
      connectionTestResult.value = response.data as ConnectionTestResult
      return response.data
    } catch (e) {
      const result: ConnectionTestResult = {
        success: false,
        message: extractDetail(e, 'Connection test failed'),
      }
      connectionTestResult.value = result
      return result
    } finally {
      isLoading.value = false
    }
  }

  async function startMigration(
    targetProvider: DatabaseProvider,
    targetUrl: string,
    confirmationText: string,
  ): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await axios.post('/api/admin/database/migrate', {
        target_provider: targetProvider,
        target_url: targetUrl,
        confirmation_text: confirmationText,
      })

      startPolling()
    } catch (e) {
      error.value = extractDetail(e, 'Migration failed to start')
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function fetchMigrationStatus(): Promise<void> {
    try {
      const response = await axios.get('/api/admin/database/migration/status')
      migrationStatus.value = response.data as MigrationStatus

      if (response.data.status === 'completed' || response.data.status === 'failed') {
        stopPolling()
        await fetchStatus()
      }
    } catch (e) {
      error.value = extractDetail(e, 'Failed to fetch migration status')
      // eslint-disable-next-line no-console
      console.error('Error fetching migration status:', e)
      useNotificationStore().showError(error.value)
    }
  }

  function startPolling(): void {
    stopPolling()
    pollingInterval.value = setInterval(fetchMigrationStatus, 2000)
    fetchMigrationStatus()
  }

  function stopPolling(): void {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  function clearError(): void {
    error.value = null
  }

  function clearMigrationStatus(): void {
    migrationStatus.value = null
  }

  async function fetchFullStatus(): Promise<unknown> {
    try {
      const response = await axios.get('/api/admin/database/full-status')
      return response.data
    } catch (e) {
      error.value = extractDetail(e, 'Failed to fetch full database status')
      // eslint-disable-next-line no-console
      console.error('Error fetching full status:', e)
      useNotificationStore().showError(error.value)
      return null
    }
  }

  return {
    currentProvider,
    migrationStatus,
    connectionInfo,
    availableProviders,
    isLoading,
    error,
    connectionTestResult,
    canMigrate,
    isMigrating,
    migrationCompleted,
    migrationFailed,
    migrationProgress,
    providerDisplayName,
    fetchStatus,
    fetchProviders,
    testConnection,
    startMigration,
    fetchMigrationStatus,
    startPolling,
    stopPolling,
    clearError,
    clearMigrationStatus,
    fetchFullStatus,
  }
})
