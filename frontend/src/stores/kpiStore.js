import { defineStore } from 'pinia'
import api from '@/services/api'
import { format, subDays } from 'date-fns'

export const useKPIStore = defineStore('kpi', {
  state: () => ({
    productionEntries: [],
    downtimeEntries: [],
    holdEntries: [],
    workOrders: [],
    downtimeReasons: [],
    dashboardData: [],
    products: [],
    shifts: [],
    loading: false,
    error: null
  }),

  getters: {
    recentEntries: (state) => state.productionEntries.slice(0, 10),
    totalUnitsToday: (state) => {
      const today = format(new Date(), 'yyyy-MM-dd')
      return state.productionEntries
        .filter(e => e.production_date === today)
        .reduce((sum, e) => sum + e.units_produced, 0)
    },
    averageEfficiency: (state) => {
      if (state.dashboardData.length === 0) return 0
      const sum = state.dashboardData.reduce((acc, d) => acc + d.avg_efficiency, 0)
      return (sum / state.dashboardData.length).toFixed(2)
    },
    averagePerformance: (state) => {
      if (state.dashboardData.length === 0) return 0
      const sum = state.dashboardData.reduce((acc, d) => acc + d.avg_performance, 0)
      return (sum / state.dashboardData.length).toFixed(2)
    }
  },

  actions: {
    async fetchProductionEntries(params = {}) {
      this.loading = true
      this.error = null

      try {
        const response = await api.getProductionEntries(params)
        this.productionEntries = response.data
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch entries'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async createProductionEntry(data) {
      this.loading = true
      this.error = null

      try {
        const response = await api.createProductionEntry(data)
        this.productionEntries.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to create entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async updateProductionEntry(id, data) {
      this.loading = true
      this.error = null

      try {
        const response = await api.updateProductionEntry(id, data)
        const index = this.productionEntries.findIndex(e => e.entry_id === id)
        if (index !== -1) {
          this.productionEntries[index] = response.data
        }
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to update entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async deleteProductionEntry(id) {
      this.loading = true
      this.error = null

      try {
        await api.deleteProductionEntry(id)
        this.productionEntries = this.productionEntries.filter(e => e.entry_id !== id)
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to delete entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async fetchKPIDashboard(days = 30) {
      this.loading = true
      this.error = null

      const endDate = format(new Date(), 'yyyy-MM-dd')
      const startDate = format(subDays(new Date(), days), 'yyyy-MM-dd')

      try {
        const response = await api.getKPIDashboard({
          start_date: startDate,
          end_date: endDate
        })
        this.dashboardData = response.data
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch dashboard'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async fetchReferenceData() {
      try {
        const [productsRes, shiftsRes, reasonsRes] = await Promise.all([
          api.getProducts(),
          api.getShifts(),
          api.getDowntimeReasons()
        ])

        this.products = productsRes.data
        this.shifts = shiftsRes.data
        this.downtimeReasons = reasonsRes.data

        // Mock work orders if not available from API
        this.workOrders = [
          { work_order_id: 1, work_order_number: 'WO-2024-001' },
          { work_order_id: 2, work_order_number: 'WO-2024-002' },
          { work_order_id: 3, work_order_number: 'WO-2024-003' }
        ]

        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch reference data'
        return { success: false, error: this.error }
      }
    },

    async uploadCSV(file) {
      this.loading = true
      this.error = null

      try {
        const response = await api.uploadCSV(file)
        await this.fetchProductionEntries()
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to upload CSV'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async batchImportProduction(entries) {
      this.loading = true
      this.error = null

      try {
        const response = await api.batchImportProduction(entries)
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to batch import'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // Downtime entry actions
    async fetchDowntimeEntries(params = {}) {
      this.loading = true
      this.error = null

      try {
        const response = await api.getDowntimeEntries(params)
        this.downtimeEntries = response.data
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch downtime entries'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async createDowntimeEntry(data) {
      this.loading = true
      this.error = null

      try {
        const response = await api.createDowntimeEntry(data)
        this.downtimeEntries.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to create downtime entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async updateDowntimeEntry(id, data) {
      this.loading = true
      this.error = null

      try {
        const response = await api.updateDowntimeEntry(id, data)
        const index = this.downtimeEntries.findIndex(e => e.downtime_id === id)
        if (index !== -1) {
          this.downtimeEntries[index] = response.data
        }
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to update downtime entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async deleteDowntimeEntry(id) {
      this.loading = true
      this.error = null

      try {
        await api.deleteDowntimeEntry(id)
        this.downtimeEntries = this.downtimeEntries.filter(e => e.downtime_id !== id)
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to delete downtime entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // Hold entry actions
    async fetchHoldEntries(params = {}) {
      this.loading = true
      this.error = null

      try {
        const response = await api.getHoldEntries(params)
        this.holdEntries = response.data
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch hold entries'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async createHoldEntry(data) {
      this.loading = true
      this.error = null

      try {
        const response = await api.createHoldEntry(data)
        this.holdEntries.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to create hold entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async updateHoldEntry(id, data) {
      this.loading = true
      this.error = null

      try {
        const response = await api.updateHoldEntry(id, data)
        const index = this.holdEntries.findIndex(e => e.hold_id === id)
        if (index !== -1) {
          this.holdEntries[index] = response.data
        }
        return { success: true, data: response.data }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to update hold entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async deleteHoldEntry(id) {
      this.loading = true
      this.error = null

      try {
        await api.deleteHoldEntry(id)
        this.holdEntries = this.holdEntries.filter(e => e.hold_id !== id)
        return { success: true }
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to delete hold entry'
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    }
  }
})
