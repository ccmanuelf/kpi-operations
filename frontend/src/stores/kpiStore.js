import { defineStore } from 'pinia'
import api from '@/services/api'
import { format, subDays } from 'date-fns'

export const useKPIStore = defineStore('kpi', {
  state: () => ({
    productionEntries: [],
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
        const [productsRes, shiftsRes] = await Promise.all([
          api.getProducts(),
          api.getShifts()
        ])

        this.products = productsRes.data
        this.shifts = shiftsRes.data

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
    }
  }
})
