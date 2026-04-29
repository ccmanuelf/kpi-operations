/**
 * Unit tests for Preferences API Service
 * Phase 8: Increase test coverage
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() }
      }
    }))
  }
}))

import * as preferencesApi from '../api/preferences'
import api from '../api/client'

describe('Preferences API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Dashboard Preferences', () => {
    describe('getDashboardPreferences', () => {
      it('fetches dashboard preferences', async () => {
        const mockPrefs = {
          data: {
            layout: 'grid',
            kpis_visible: ['efficiency', 'oee', 'ppm'],
            refresh_interval: 30
          }
        }
        api.get.mockResolvedValueOnce(mockPrefs)

        const result = await preferencesApi.getDashboardPreferences()

        expect(api.get).toHaveBeenCalledWith('/preferences/dashboard')
        expect(result).toEqual(mockPrefs)
      })
    })

    describe('saveDashboardPreferences', () => {
      it('saves complete dashboard preferences', async () => {
        const prefs = {
          layout: 'list',
          kpis_visible: ['efficiency'],
          refresh_interval: 60
        }
        api.put.mockResolvedValueOnce({ data: prefs })

        await preferencesApi.saveDashboardPreferences(prefs)

        expect(api.put).toHaveBeenCalledWith('/preferences/dashboard', prefs)
      })
    })

    describe('updateDashboardPreferences', () => {
      it('patches dashboard preferences', async () => {
        const updates = { refresh_interval: 120 }
        api.patch.mockResolvedValueOnce({ data: updates })

        await preferencesApi.updateDashboardPreferences(updates)

        expect(api.patch).toHaveBeenCalledWith('/preferences/dashboard', updates)
      })
    })

    describe('getDashboardDefaults', () => {
      it('fetches defaults for operator role', async () => {
        api.get.mockResolvedValueOnce({ data: {} })

        await preferencesApi.getDashboardDefaults('operator')

        expect(api.get).toHaveBeenCalledWith('/preferences/defaults/operator')
      })

      it('fetches defaults for admin role', async () => {
        api.get.mockResolvedValueOnce({ data: {} })

        await preferencesApi.getDashboardDefaults('admin')

        expect(api.get).toHaveBeenCalledWith('/preferences/defaults/admin')
      })
    })

    describe('resetDashboardPreferences', () => {
      it('resets preferences to defaults', async () => {
        api.post.mockResolvedValueOnce({ data: { reset: true } })

        await preferencesApi.resetDashboardPreferences()

        expect(api.post).toHaveBeenCalledWith('/preferences/reset')
      })
    })
  })

  describe('Saved Filters', () => {
    describe('getSavedFilters', () => {
      it('fetches saved filters with params', async () => {
        const mockFilters = {
          data: [
            { id: 1, name: 'Production Filter' },
            { id: 2, name: 'Quality Filter' }
          ]
        }
        api.get.mockResolvedValueOnce(mockFilters)

        const result = await preferencesApi.getSavedFilters({ category: 'production' })

        expect(api.get).toHaveBeenCalledWith('/filters', { params: { category: 'production' } })
        expect(result).toEqual(mockFilters)
      })
    })

    describe('createSavedFilter', () => {
      it('creates new filter', async () => {
        const newFilter = {
          name: 'My Filter',
          filters: { client_id: 1, shift_id: 1 }
        }
        api.post.mockResolvedValueOnce({ data: { id: 3, ...newFilter } })

        await preferencesApi.createSavedFilter(newFilter)

        expect(api.post).toHaveBeenCalledWith('/filters', newFilter)
      })
    })

    describe('getSavedFilter', () => {
      it('fetches single filter by ID', async () => {
        api.get.mockResolvedValueOnce({ data: { id: 1, name: 'Filter' } })

        await preferencesApi.getSavedFilter(1)

        expect(api.get).toHaveBeenCalledWith('/filters/1')
      })
    })

    describe('updateSavedFilter', () => {
      it('updates existing filter', async () => {
        const updates = { name: 'Updated Filter' }
        api.put.mockResolvedValueOnce({ data: { id: 1, ...updates } })

        await preferencesApi.updateSavedFilter(1, updates)

        expect(api.put).toHaveBeenCalledWith('/filters/1', updates)
      })
    })

    describe('deleteSavedFilter', () => {
      it('deletes filter by ID', async () => {
        api.delete.mockResolvedValueOnce({ data: { success: true } })

        await preferencesApi.deleteSavedFilter(1)

        expect(api.delete).toHaveBeenCalledWith('/filters/1')
      })
    })

    describe('applyFilter', () => {
      it('applies filter by ID', async () => {
        api.post.mockResolvedValueOnce({ data: { applied: true } })

        await preferencesApi.applyFilter(1)

        expect(api.post).toHaveBeenCalledWith('/filters/1/apply')
      })
    })

    describe('setDefaultFilter', () => {
      it('sets filter as default', async () => {
        api.post.mockResolvedValueOnce({ data: { is_default: true } })

        await preferencesApi.setDefaultFilter(1)

        expect(api.post).toHaveBeenCalledWith('/filters/1/set-default')
      })
    })

    describe('duplicateFilter', () => {
      it('duplicates filter with new name', async () => {
        api.post.mockResolvedValueOnce({ data: { id: 4, name: 'Copy of Filter' } })

        await preferencesApi.duplicateFilter(1, 'Copy of Filter')

        expect(api.post).toHaveBeenCalledWith('/filters/1/duplicate', { new_name: 'Copy of Filter' })
      })
    })

    describe('getFilterHistory', () => {
      it('fetches recent filter history', async () => {
        api.get.mockResolvedValueOnce({ data: [] })

        await preferencesApi.getFilterHistory()

        expect(api.get).toHaveBeenCalledWith('/filters/history/recent')
      })
    })

    describe('clearFilterHistory', () => {
      it('clears filter history', async () => {
        api.delete.mockResolvedValueOnce({ data: { cleared: true } })

        await preferencesApi.clearFilterHistory()

        expect(api.delete).toHaveBeenCalledWith('/filters/history')
      })
    })
  })
})
