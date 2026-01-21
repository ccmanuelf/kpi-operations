import { defineStore } from 'pinia'
import api from '@/services/api'

export const useKPIStore = defineStore('kpi', {
  state: () => ({
    dashboard: null,
    selectedClient: null,
    dateRange: {
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      end: new Date().toISOString().split('T')[0]
    },
    efficiency: null,
    wipAging: null,
    onTimeDelivery: null,
    availability: null,
    performance: null,
    quality: null,
    oee: null,
    absenteeism: null,
    defectRates: null,
    throughputTime: null,
    trends: {
      efficiency: [],
      wipAging: [],
      onTimeDelivery: [],
      availability: [],
      performance: [],
      quality: [],
      oee: [],
      absenteeism: []
    },
    // Predictions state
    predictions: {
      efficiency: null,
      performance: null,
      availability: null,
      oee: null,
      quality: null,
      absenteeism: null,
      otd: null,
      fpy: null,
      rty: null,
      ppm: null,
      dpmo: null
    },
    allPredictions: null,
    benchmarks: null,
    loading: false,
    error: null
  }),

  getters: {
    kpiStatus: (state) => (value, target, isHigherBetter = true) => {
      if (!value || !target) return 'gray'
      const percentage = (value / target) * 100
      if (isHigherBetter) {
        if (percentage >= 95) return 'success'
        if (percentage >= 80) return 'warning'
        return 'error'
      } else {
        if (percentage <= 5) return 'success'
        if (percentage <= 20) return 'warning'
        return 'error'
      }
    },

    kpiIcon: (state) => (value, target, isHigherBetter = true) => {
      if (!value || !target) return 'mdi-minus-circle'
      const percentage = (value / target) * 100
      if (isHigherBetter) {
        if (percentage >= 95) return 'mdi-check-circle'
        if (percentage >= 80) return 'mdi-alert-circle'
        return 'mdi-close-circle'
      } else {
        if (percentage <= 5) return 'mdi-check-circle'
        if (percentage <= 20) return 'mdi-alert-circle'
        return 'mdi-close-circle'
      }
    },

    allKPIs: (state) => [
      {
        key: 'efficiency',
        title: 'Efficiency',
        value: state.efficiency?.current,
        target: state.efficiency?.target || 85,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-chart-line',
        route: '/kpi/efficiency'
      },
      {
        key: 'wipAging',
        title: 'WIP Aging',
        value: state.wipAging?.average_days,
        target: 7,
        unit: 'days',
        higherBetter: false,
        icon: 'mdi-clock-alert',
        route: '/kpi/wip-aging'
      },
      {
        key: 'onTimeDelivery',
        title: 'On-Time Delivery',
        value: state.onTimeDelivery?.percentage,
        target: 95,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-truck-delivery',
        route: '/kpi/on-time-delivery'
      },
      {
        key: 'availability',
        title: 'Availability',
        value: state.availability?.percentage,
        target: 90,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-server',
        route: '/kpi/availability'
      },
      {
        key: 'performance',
        title: 'Performance',
        value: state.performance?.percentage,
        target: 95,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-speedometer',
        route: '/kpi/performance'
      },
      {
        key: 'quality',
        title: 'Quality (FPY)',
        value: state.quality?.fpy,
        target: 99,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-star-circle',
        route: '/kpi/quality'
      },
      {
        key: 'oee',
        title: 'OEE',
        value: state.oee?.percentage,
        target: 85,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-factory',
        route: '/kpi/oee'
      },
      {
        key: 'absenteeism',
        title: 'Absenteeism',
        value: state.absenteeism?.rate,
        target: 5,
        unit: '%',
        higherBetter: false,
        icon: 'mdi-account-alert',
        route: '/kpi/absenteeism'
      },
      {
        key: 'defectRates',
        title: 'PPM',
        value: state.defectRates?.ppm,
        target: 500,
        unit: 'ppm',
        higherBetter: false,
        icon: 'mdi-alert-circle',
        route: '/kpi/quality',
        subtitle: state.defectRates?.defect_rate_percentage != null
          ? `${state.defectRates.defect_rate_percentage}% defect rate`
          : null
      },
      {
        key: 'throughputTime',
        title: 'Throughput Time',
        value: state.throughputTime?.average_hours,
        target: 24,
        unit: 'hrs',
        higherBetter: false,
        icon: 'mdi-timer',
        route: '/kpi/efficiency'
      }
    ]
  },

  actions: {
    setClient(clientId) {
      this.selectedClient = clientId
    },

    setDateRange(start, end) {
      this.dateRange = { start, end }
    },

    // Helper to build query params without null values
    _buildParams() {
      const params = {
        start_date: this.dateRange.start,
        end_date: this.dateRange.end
      }
      if (this.selectedClient) {
        params.client_id = this.selectedClient
      }
      return params
    },

    async fetchDashboard() {
      this.loading = true
      this.error = null
      try {
        const params = this._buildParams()
        const response = await api.getKPIDashboard(params)
        this.dashboard = response.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch dashboard'
        console.error('Dashboard fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchEfficiency() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getEfficiency(params),
          api.getEfficiencyTrend(params)
        ])
        this.efficiency = dataRes.data
        this.trends.efficiency = trendRes.data || []
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch efficiency'
        console.error('Efficiency fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchWIPAging() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getWIPAging(params),
          api.getWIPAgingTrend(params)
        ])
        this.wipAging = dataRes.data
        this.trends.wipAging = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch WIP aging'
        console.error('WIP Aging fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchOnTimeDelivery() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getOnTimeDelivery(params),
          api.getOnTimeDeliveryTrend(params)
        ])
        this.onTimeDelivery = dataRes.data
        this.trends.onTimeDelivery = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch on-time delivery'
        console.error('On-time delivery fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchAvailability() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getAvailability(params),
          api.getAvailabilityTrend(params)
        ])
        this.availability = dataRes.data
        this.trends.availability = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch availability'
        console.error('Availability fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchPerformance() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getPerformance(params),
          api.getPerformanceTrend(params)
        ])
        this.performance = dataRes.data
        this.trends.performance = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch performance'
        console.error('Performance fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchQuality() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getQuality(params),
          api.getQualityTrend(params)
        ])
        this.quality = dataRes.data
        this.trends.quality = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch quality'
        console.error('Quality fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchOEE() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getOEE(params),
          api.getOEETrend(params)
        ])
        this.oee = dataRes.data
        this.trends.oee = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch OEE'
        console.error('OEE fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchAbsenteeism() {
      this.loading = true
      try {
        const params = this._buildParams()
        const [dataRes, trendRes] = await Promise.all([
          api.getAbsenteeism(params),
          api.getAbsenteeismTrend(params)
        ])
        this.absenteeism = dataRes.data
        this.trends.absenteeism = trendRes.data
        return dataRes.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch absenteeism'
        console.error('Absenteeism fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchDefectRates() {
      this.loading = true
      try {
        const params = this._buildParams()
        const response = await api.getDefectRates(params)
        this.defectRates = response.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch defect rates'
        console.error('Defect rates fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchThroughputTime() {
      this.loading = true
      try {
        const params = this._buildParams()
        const response = await api.getThroughputTime(params)
        this.throughputTime = response.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch throughput time'
        console.error('Throughput time fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchAllKPIs() {
      this.loading = true
      try {
        await Promise.all([
          this.fetchEfficiency(),
          this.fetchWIPAging(),
          this.fetchOnTimeDelivery(),
          this.fetchAvailability(),
          this.fetchPerformance(),
          this.fetchQuality(),
          this.fetchOEE(),
          this.fetchAbsenteeism(),
          this.fetchDefectRates(),
          this.fetchThroughputTime()
        ])
      } catch (error) {
        console.error('Error fetching all KPIs:', error)
      } finally {
        this.loading = false
      }
    },

    // ============================================
    // Predictions Actions
    // ============================================

    /**
     * Fetch prediction for a specific KPI
     * @param {string} kpiType - Type of KPI (efficiency, performance, availability, oee, ppm, dpmo, fpy, rty, absenteeism, otd)
     * @param {number} forecastDays - Number of days to forecast (1-30), default 7
     * @param {number} historicalDays - Number of historical days to use (7-90), default 30
     * @param {string} method - Forecasting method (auto, simple, double, linear), default auto
     */
    async fetchPrediction(kpiType, forecastDays = 7, historicalDays = 30, method = 'auto') {
      this.loading = true
      try {
        const params = {
          ...this._buildParams(),
          forecast_days: forecastDays,
          historical_days: historicalDays,
          method: method
        }
        const response = await api.getPrediction(kpiType, params)

        // Map KPI type to predictions state key
        const keyMap = {
          'efficiency': 'efficiency',
          'performance': 'performance',
          'availability': 'availability',
          'oee': 'oee',
          'quality': 'quality',
          'fpy': 'fpy',
          'rty': 'rty',
          'ppm': 'ppm',
          'dpmo': 'dpmo',
          'absenteeism': 'absenteeism',
          'otd': 'otd'
        }

        const stateKey = keyMap[kpiType] || kpiType
        this.predictions[stateKey] = response.data
        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || `Failed to fetch ${kpiType} prediction`
        console.error(`Prediction fetch error for ${kpiType}:`, error)
        return null
      } finally {
        this.loading = false
      }
    },

    /**
     * Fetch predictions for all KPIs at once
     * @param {number} forecastDays - Number of days to forecast (1-30), default 7
     * @param {number} historicalDays - Number of historical days to use (7-90), default 30
     */
    async fetchAllPredictions(forecastDays = 7, historicalDays = 30) {
      this.loading = true
      try {
        const params = {
          ...this._buildParams(),
          forecast_days: forecastDays,
          historical_days: historicalDays
        }
        const response = await api.getAllPredictions(params)
        this.allPredictions = response.data

        // Also populate individual predictions from the response
        if (response.data) {
          const kpiTypes = ['efficiency', 'performance', 'availability', 'oee', 'ppm', 'dpmo', 'fpy', 'rty', 'absenteeism', 'otd']
          kpiTypes.forEach(kpi => {
            if (response.data[kpi]) {
              this.predictions[kpi] = response.data[kpi]
            }
          })
        }

        return response.data
      } catch (error) {
        this.error = error.response?.data?.detail || 'Failed to fetch all predictions'
        console.error('All predictions fetch error:', error)
        return null
      } finally {
        this.loading = false
      }
    },

    /**
     * Fetch KPI benchmarks
     */
    async fetchBenchmarks() {
      try {
        const response = await api.getPredictionBenchmarks()
        this.benchmarks = response.data
        return response.data
      } catch (error) {
        console.error('Benchmarks fetch error:', error)
        return null
      }
    },

    /**
     * Get quick health assessment for a KPI
     * @param {string} kpiType - Type of KPI
     */
    async fetchKPIHealth(kpiType) {
      try {
        const params = this._buildParams()
        const response = await api.getKPIHealth(kpiType, params)
        return response.data
      } catch (error) {
        console.error(`Health fetch error for ${kpiType}:`, error)
        return null
      }
    },

    /**
     * Helper to generate forecast chart dataset
     * @param {Object} prediction - Prediction response from API
     * @param {string} color - Color for the forecast line
     */
    getForecastChartData(prediction, color = '#9c27b0') {
      if (!prediction || !prediction.predictions) {
        return null
      }

      const forecastLabels = prediction.predictions.map(p => {
        const date = new Date(p.date)
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      })

      const forecastValues = prediction.predictions.map(p => p.predicted_value)
      const lowerBounds = prediction.predictions.map(p => p.lower_bound)
      const upperBounds = prediction.predictions.map(p => p.upper_bound)

      return {
        labels: forecastLabels,
        datasets: [
          {
            label: 'Forecast',
            data: forecastValues,
            borderColor: color,
            backgroundColor: `${color}20`,
            borderDash: [5, 5],
            tension: 0.3,
            fill: false,
            pointStyle: 'rectRot',
            pointRadius: 4
          },
          {
            label: 'Confidence Upper',
            data: upperBounds,
            borderColor: `${color}50`,
            backgroundColor: `${color}10`,
            borderDash: [2, 2],
            tension: 0.3,
            fill: '+1',
            pointRadius: 0
          },
          {
            label: 'Confidence Lower',
            data: lowerBounds,
            borderColor: `${color}50`,
            backgroundColor: 'transparent',
            borderDash: [2, 2],
            tension: 0.3,
            fill: false,
            pointRadius: 0
          }
        ]
      }
    }
  }
})
