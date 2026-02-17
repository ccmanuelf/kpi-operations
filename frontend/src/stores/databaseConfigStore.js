/**
 * Database Configuration Store
 *
 * Pinia store for managing database configuration state and migration operations.
 * Provides reactive state for current provider, migration status, and polling.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { useNotificationStore } from '@/stores/notificationStore'

export const useDatabaseConfigStore = defineStore('databaseConfig', () => {
  // ============================================================================
  // State
  // ============================================================================

  const currentProvider = ref('sqlite')
  const migrationStatus = ref(null)
  const connectionInfo = ref({})
  const availableProviders = ref({})
  const isLoading = ref(false)
  const error = ref(null)
  const pollingInterval = ref(null)
  const connectionTestResult = ref(null)

  // ============================================================================
  // Computed
  // ============================================================================

  /**
   * Check if migration is available (only from SQLite)
   */
  const canMigrate = computed(() => currentProvider.value === 'sqlite')

  /**
   * Check if migration is currently in progress
   */
  const isMigrating = computed(() =>
    migrationStatus.value?.status === 'in_progress'
  )

  /**
   * Check if migration completed successfully
   */
  const migrationCompleted = computed(() =>
    migrationStatus.value?.status === 'completed'
  )

  /**
   * Check if migration failed
   */
  const migrationFailed = computed(() =>
    migrationStatus.value?.status === 'failed'
  )

  /**
   * Get migration progress percentage
   */
  const migrationProgress = computed(() => {
    if (!migrationStatus.value) return 0
    const { tables_migrated, total_tables } = migrationStatus.value
    return total_tables > 0 ? Math.round((tables_migrated / total_tables) * 100) : 0
  })

  /**
   * Get provider display name
   */
  const providerDisplayName = computed(() => {
    const names = {
      sqlite: 'SQLite',
      mariadb: 'MariaDB',
      mysql: 'MySQL',
      postgresql: 'PostgreSQL'
    }
    return names[currentProvider.value] || currentProvider.value.toUpperCase()
  })

  // ============================================================================
  // Actions
  // ============================================================================

  /**
   * Fetch current database status
   */
  async function fetchStatus() {
    isLoading.value = true
    error.value = null

    try {
      const response = await axios.get('/api/admin/database/status')
      currentProvider.value = response.data.current_provider
      connectionInfo.value = response.data.connection_info || {}
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to fetch database status'
      console.error('Error fetching database status:', e)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch available providers information
   */
  async function fetchProviders() {
    try {
      const response = await axios.get('/api/admin/database/providers')
      availableProviders.value = response.data.providers
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to fetch database providers'
      console.error('Error fetching providers:', e)
      useNotificationStore().showError(error.value)
    }
  }

  /**
   * Test connection to a database URL
   * @param {string} targetUrl - Database connection URL
   * @returns {Promise<Object>} Connection test result
   */
  async function testConnection(targetUrl) {
    isLoading.value = true
    connectionTestResult.value = null

    try {
      const response = await axios.post('/api/admin/database/test-connection', {
        target_url: targetUrl
      })
      connectionTestResult.value = response.data
      return response.data
    } catch (e) {
      const result = {
        success: false,
        message: e.response?.data?.detail || 'Connection test failed'
      }
      connectionTestResult.value = result
      return result
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Start database migration
   * @param {string} targetProvider - Target provider (mariadb, mysql)
   * @param {string} targetUrl - Database connection URL
   * @param {string} confirmationText - Must be 'MIGRATE'
   */
  async function startMigration(targetProvider, targetUrl, confirmationText) {
    isLoading.value = true
    error.value = null

    try {
      await axios.post('/api/admin/database/migrate', {
        target_provider: targetProvider,
        target_url: targetUrl,
        confirmation_text: confirmationText
      })

      // Start polling for migration status
      startPolling()
    } catch (e) {
      error.value = e.response?.data?.detail || 'Migration failed to start'
      throw e
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Fetch current migration status
   */
  async function fetchMigrationStatus() {
    try {
      const response = await axios.get('/api/admin/database/migration/status')
      migrationStatus.value = response.data

      // Stop polling if migration completed or failed
      if (response.data.status === 'completed' || response.data.status === 'failed') {
        stopPolling()
        // Refresh main status after migration
        await fetchStatus()
      }
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to fetch migration status'
      console.error('Error fetching migration status:', e)
      useNotificationStore().showError(error.value)
    }
  }

  /**
   * Start polling for migration status updates
   */
  function startPolling() {
    stopPolling() // Clear any existing interval
    pollingInterval.value = setInterval(fetchMigrationStatus, 2000)
    // Fetch immediately
    fetchMigrationStatus()
  }

  /**
   * Stop polling for migration status
   */
  function stopPolling() {
    if (pollingInterval.value) {
      clearInterval(pollingInterval.value)
      pollingInterval.value = null
    }
  }

  /**
   * Clear error state
   */
  function clearError() {
    error.value = null
  }

  /**
   * Reset migration status (after viewing results)
   */
  function clearMigrationStatus() {
    migrationStatus.value = null
  }

  /**
   * Get full status including migration history
   * @returns {Promise<Object>} Full status object
   */
  async function fetchFullStatus() {
    try {
      const response = await axios.get('/api/admin/database/full-status')
      return response.data
    } catch (e) {
      error.value = e.response?.data?.detail || 'Failed to fetch full database status'
      console.error('Error fetching full status:', e)
      useNotificationStore().showError(error.value)
      return null
    }
  }

  // ============================================================================
  // Return store interface
  // ============================================================================

  return {
    // State
    currentProvider,
    migrationStatus,
    connectionInfo,
    availableProviders,
    isLoading,
    error,
    connectionTestResult,

    // Computed
    canMigrate,
    isMigrating,
    migrationCompleted,
    migrationFailed,
    migrationProgress,
    providerDisplayName,

    // Actions
    fetchStatus,
    fetchProviders,
    testConnection,
    startMigration,
    fetchMigrationStatus,
    startPolling,
    stopPolling,
    clearError,
    clearMigrationStatus,
    fetchFullStatus
  }
})
