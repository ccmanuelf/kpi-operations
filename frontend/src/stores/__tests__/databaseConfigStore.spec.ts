/**
 * Unit tests for Database Config Store
 *
 * Regression guard for ISSUE-020: the admin Database Config screen got 401s
 * with a valid admin session because this store called a bare axios
 * instance (no Authorization header) instead of the shared authed client
 * (`@/services/api`, which attaches `Authorization: Bearer <token>` via an
 * interceptor). These tests assert the store calls the shared client.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock the shared authed API client
vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}))

// Mock the notification store (fetchStatus/fetchProviders call showError on failure)
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn(() => ({
    showError: vi.fn(),
  })),
}))

import api from '@/services/api'
import { useDatabaseConfigStore } from '../databaseConfigStore'

describe('Database Config Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetchStatus calls the shared authed api client (not bare axios)', async () => {
    api.get.mockResolvedValue({
      data: { current_provider: 'mariadb', connection_info: { host: 'db', provider: 'mariadb' } },
    })

    const store = useDatabaseConfigStore()
    await store.fetchStatus()

    expect(api.get).toHaveBeenCalledWith('/admin/database/status')
    expect(store.currentProvider).toBe('mariadb')
    expect(store.connectionInfo).toEqual({ host: 'db', provider: 'mariadb' })
  })

  it('fetchProviders calls the shared authed api client (not bare axios)', async () => {
    api.get.mockResolvedValue({
      data: { providers: { sqlite: { available: true }, mariadb: { available: true } } },
    })

    const store = useDatabaseConfigStore()
    await store.fetchProviders()

    expect(api.get).toHaveBeenCalledWith('/admin/database/providers')
    expect(store.availableProviders).toEqual({
      sqlite: { available: true },
      mariadb: { available: true },
    })
  })

  it('surfaces a 401 from the shared client as a store error instead of throwing', async () => {
    api.get.mockRejectedValue({ response: { status: 401, data: { detail: 'Not authenticated' } } })

    const store = useDatabaseConfigStore()
    await store.fetchStatus()

    expect(store.error).toBe('Not authenticated')
  })
})
