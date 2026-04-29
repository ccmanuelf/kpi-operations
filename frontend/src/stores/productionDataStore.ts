import { defineStore } from 'pinia'
import api from '@/services/api'
import { format, subDays } from 'date-fns'

type Payload = Record<string, unknown>
type Params = Record<string, unknown>

export interface ProductionEntry {
  entry_id?: number | string
  production_date?: string
  units_produced?: number
  efficiency_percentage?: number | string | null
  performance_percentage?: number | string | null
  [key: string]: unknown
}

export interface DowntimeEntry {
  downtime_id?: number | string
  [key: string]: unknown
}

export interface HoldEntry {
  hold_id?: number | string
  [key: string]: unknown
}

export interface WorkOrder {
  work_order_id: number | string
  work_order_number: string
  [key: string]: unknown
}

export interface DowntimeReason {
  [key: string]: unknown
}

export interface DashboardRow {
  [key: string]: unknown
}

export interface Product {
  [key: string]: unknown
}

export interface Shift {
  [key: string]: unknown
}

export interface ProductionDataState {
  productionEntries: ProductionEntry[]
  downtimeEntries: DowntimeEntry[]
  holdEntries: HoldEntry[]
  workOrders: WorkOrder[]
  downtimeReasons: DowntimeReason[]
  dashboardData: DashboardRow[]
  products: Product[]
  shifts: Shift[]
  loading: boolean
  error: string | null
}

export interface ActionResult<T = unknown> {
  success: boolean
  error?: string
  data?: T
}

const extractDetail = (error: unknown, fallback: string): string => {
  const ax = error as { response?: { data?: { detail?: string } } }
  return ax?.response?.data?.detail || fallback
}

export const useProductionDataStore = defineStore('productionData', {
  state: (): ProductionDataState => ({
    productionEntries: [],
    downtimeEntries: [],
    holdEntries: [],
    workOrders: [],
    downtimeReasons: [],
    dashboardData: [],
    products: [],
    shifts: [],
    loading: false,
    error: null,
  }),

  getters: {
    recentEntries: (state): ProductionEntry[] => state.productionEntries.slice(0, 10),
    totalUnitsToday: (state): number => {
      const today = format(new Date(), 'yyyy-MM-dd')
      return state.productionEntries
        .filter((e) => {
          const entryDate = e.production_date?.split('T')[0]
          return entryDate === today
        })
        .reduce((sum, e) => sum + (e.units_produced || 0), 0)
    },
    // The JS version returned `0` (number) for the empty/no-valid
    // cases and a `string` from `.toFixed(2)` otherwise. Existing
    // tests pin that exact return-type inconsistency, so the union
    // is preserved here rather than coerced.
    averageEfficiency: (state): number | string => {
      if (state.productionEntries.length === 0) return 0
      const validEntries = state.productionEntries.filter(
        (e) => e.efficiency_percentage != null,
      )
      if (validEntries.length === 0) return 0
      const sum = validEntries.reduce(
        (acc, e) => acc + parseFloat(String(e.efficiency_percentage ?? 0)),
        0,
      )
      return (sum / validEntries.length).toFixed(2)
    },
    averagePerformance: (state): number | string => {
      if (state.productionEntries.length === 0) return 0
      const validEntries = state.productionEntries.filter(
        (e) => e.performance_percentage != null,
      )
      if (validEntries.length === 0) return 0
      const sum = validEntries.reduce(
        (acc, e) => acc + parseFloat(String(e.performance_percentage ?? 0)),
        0,
      )
      return (sum / validEntries.length).toFixed(2)
    },
  },

  actions: {
    async fetchProductionEntries(params: Params = {}): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        const response = await api.getProductionEntries(params)
        this.productionEntries = response.data
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] fetchProductionEntries failed:', error)
        this.error = extractDetail(error, 'Failed to fetch entries')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async createProductionEntry(data: Payload): Promise<ActionResult<ProductionEntry>> {
      this.loading = true
      this.error = null
      try {
        const response = await api.createProductionEntry(data)
        this.productionEntries.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] createProductionEntry failed:', error)
        this.error = extractDetail(error, 'Failed to create entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async updateProductionEntry(
      id: string | number,
      data: Payload,
    ): Promise<ActionResult<ProductionEntry>> {
      this.loading = true
      this.error = null
      try {
        const response = await api.updateProductionEntry(id, data)
        const index = this.productionEntries.findIndex((e) => e.entry_id === id)
        if (index !== -1) {
          this.productionEntries[index] = response.data
        }
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] updateProductionEntry failed:', error)
        this.error = extractDetail(error, 'Failed to update entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async deleteProductionEntry(id: string | number): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        await api.deleteProductionEntry(id)
        this.productionEntries = this.productionEntries.filter((e) => e.entry_id !== id)
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] deleteProductionEntry failed:', error)
        this.error = extractDetail(error, 'Failed to delete entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async fetchKPIDashboard(days = 30, additionalParams: Params = {}): Promise<ActionResult> {
      this.loading = true
      this.error = null

      const endDate = format(new Date(), 'yyyy-MM-dd')
      const startDate = format(subDays(new Date(), days), 'yyyy-MM-dd')

      try {
        const response = await api.getKPIDashboard({
          start_date: startDate,
          end_date: endDate,
          ...additionalParams,
        })
        this.dashboardData = response.data
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] fetchKPIDashboard failed:', error)
        this.error = extractDetail(error, 'Failed to fetch dashboard')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async fetchReferenceData(): Promise<ActionResult> {
      try {
        const [productsRes, shiftsRes, reasonsRes] = await Promise.all([
          api.getProducts(),
          api.getShifts(),
          api.getDowntimeReasons(),
        ])

        this.products = productsRes.data
        this.shifts = shiftsRes.data
        this.downtimeReasons = reasonsRes.data

        this.workOrders = [
          { work_order_id: 1, work_order_number: 'WO-2024-001' },
          { work_order_id: 2, work_order_number: 'WO-2024-002' },
          { work_order_id: 3, work_order_number: 'WO-2024-003' },
        ]

        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] fetchReferenceData failed:', error)
        this.error = extractDetail(error, 'Failed to fetch reference data')
        return { success: false, error: this.error }
      }
    },

    async uploadCSV(file: File): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        const response = await api.uploadCSV(file)
        await this.fetchProductionEntries()
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] uploadCSV failed:', error)
        this.error = extractDetail(error, 'Failed to upload CSV')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async batchImportProduction(entries: Payload[]): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        const response = await api.batchImportProduction(entries)
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] batchImportProduction failed:', error)
        this.error = extractDetail(error, 'Failed to batch import')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // Downtime entry actions
    async fetchDowntimeEntries(params: Params = {}): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        const response = await api.getDowntimeEntries(params)
        this.downtimeEntries = response.data
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] fetchDowntimeEntries failed:', error)
        this.error = extractDetail(error, 'Failed to fetch downtime entries')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async createDowntimeEntry(data: Payload): Promise<ActionResult<DowntimeEntry>> {
      this.loading = true
      this.error = null
      try {
        const response = await api.createDowntimeEntry(data)
        this.downtimeEntries.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] createDowntimeEntry failed:', error)
        this.error = extractDetail(error, 'Failed to create downtime entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async updateDowntimeEntry(
      id: string | number,
      data: Payload,
    ): Promise<ActionResult<DowntimeEntry>> {
      this.loading = true
      this.error = null
      try {
        const response = await api.updateDowntimeEntry(id, data)
        const index = this.downtimeEntries.findIndex((e) => e.downtime_id === id)
        if (index !== -1) {
          this.downtimeEntries[index] = response.data
        }
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] updateDowntimeEntry failed:', error)
        this.error = extractDetail(error, 'Failed to update downtime entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async deleteDowntimeEntry(id: string | number): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        await api.deleteDowntimeEntry(id)
        this.downtimeEntries = this.downtimeEntries.filter((e) => e.downtime_id !== id)
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] deleteDowntimeEntry failed:', error)
        this.error = extractDetail(error, 'Failed to delete downtime entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    // Hold entry actions
    async fetchHoldEntries(params: Params = {}): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        const response = await api.getHoldEntries(params)
        this.holdEntries = response.data
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] fetchHoldEntries failed:', error)
        this.error = extractDetail(error, 'Failed to fetch hold entries')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async createHoldEntry(data: Payload): Promise<ActionResult<HoldEntry>> {
      this.loading = true
      this.error = null
      try {
        const response = await api.createHoldEntry(data)
        this.holdEntries.unshift(response.data)
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] createHoldEntry failed:', error)
        this.error = extractDetail(error, 'Failed to create hold entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async updateHoldEntry(
      id: string | number,
      data: Payload,
    ): Promise<ActionResult<HoldEntry>> {
      this.loading = true
      this.error = null
      try {
        const response = await api.updateHoldEntry(id, data)
        const index = this.holdEntries.findIndex((e) => e.hold_id === id)
        if (index !== -1) {
          this.holdEntries[index] = response.data
        }
        return { success: true, data: response.data }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] updateHoldEntry failed:', error)
        this.error = extractDetail(error, 'Failed to update hold entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },

    async deleteHoldEntry(id: string | number): Promise<ActionResult> {
      this.loading = true
      this.error = null
      try {
        await api.deleteHoldEntry(id)
        this.holdEntries = this.holdEntries.filter((e) => e.hold_id !== id)
        return { success: true }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('[ProductionDataStore] deleteHoldEntry failed:', error)
        this.error = extractDetail(error, 'Failed to delete hold entry')
        return { success: false, error: this.error }
      } finally {
        this.loading = false
      }
    },
  },
})
