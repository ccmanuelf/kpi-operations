/**
 * Aggregate KPI store — pulls each of the 10 KPIs (efficiency,
 * WIP aging, OTD, availability, performance, quality, OEE,
 * absenteeism, defect rates, throughput time) and their trends/
 * predictions. Options-API style.
 */
import { defineStore } from 'pinia'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notificationStore'

export type KPIKey =
  | 'efficiency'
  | 'wipAging'
  | 'onTimeDelivery'
  | 'availability'
  | 'performance'
  | 'quality'
  | 'oee'
  | 'absenteeism'
  | 'defectRates'
  | 'throughputTime'

export type PredictionKey =
  | 'efficiency'
  | 'performance'
  | 'availability'
  | 'oee'
  | 'quality'
  | 'fpy'
  | 'rty'
  | 'ppm'
  | 'dpmo'
  | 'absenteeism'
  | 'otd'

export type ForecastMethod = 'auto' | 'simple' | 'double' | 'linear'
export type StatusColor = 'success' | 'warning' | 'error' | 'gray'
export type StatusIcon =
  | 'mdi-check-circle'
  | 'mdi-alert-circle'
  | 'mdi-close-circle'
  | 'mdi-minus-circle'

export interface InferenceData {
  is_estimated: boolean
  confidence_score: number
  details: Record<string, unknown>
}

export interface DateRange {
  start: string
  end: string
}

export interface KPIPayload {
  current?: number | null
  percentage?: number | null
  rate?: number | null
  ppm?: number | null
  defect_rate_percentage?: number | null
  fpy?: number | null
  average_days?: number | null
  average_hours?: number | null
  target?: number | null
  inference?: Partial<InferenceData>
  was_inferred?: boolean
  has_estimated?: boolean
  data_quality?: number
  cycle_time?: unknown
  employees?: unknown
  scheduled_hours?: unknown
  [key: string]: unknown
}

export interface KPISummary {
  key: KPIKey
  title: string
  value: number | null | undefined
  target: number
  unit: string
  higherBetter: boolean
  icon: string
  route: string
  inference: InferenceData
  subtitle?: string | null
}

export interface PredictionPoint {
  date: string
  predicted_value: number
  lower_bound: number
  upper_bound: number
}

export interface PredictionResponse {
  predictions?: PredictionPoint[]
  [key: string]: unknown
}

export interface ChartDataset {
  label: string
  data: number[]
  borderColor: string
  backgroundColor: string
  borderDash?: number[]
  tension: number
  fill: boolean | string
  pointStyle?: string
  pointRadius: number
}

export interface ChartData {
  labels: string[]
  datasets: ChartDataset[]
}

interface InferenceMap {
  efficiency: InferenceData
  wipAging: InferenceData
  onTimeDelivery: InferenceData
  availability: InferenceData
  performance: InferenceData
  quality: InferenceData
  oee: InferenceData
  absenteeism: InferenceData
  defectRates: InferenceData
  throughputTime: InferenceData
}

interface TrendsMap {
  efficiency: unknown[]
  wipAging: unknown[]
  onTimeDelivery: unknown[]
  availability: unknown[]
  performance: unknown[]
  quality: unknown[]
  oee: unknown[]
  absenteeism: unknown[]
}

interface PredictionsMap {
  efficiency: PredictionResponse | null
  performance: PredictionResponse | null
  availability: PredictionResponse | null
  oee: PredictionResponse | null
  quality: PredictionResponse | null
  absenteeism: PredictionResponse | null
  otd: PredictionResponse | null
  fpy: PredictionResponse | null
  rty: PredictionResponse | null
  ppm: PredictionResponse | null
  dpmo: PredictionResponse | null
}

interface KPIState {
  dashboard: unknown | null
  selectedClient: string | number | null
  dateRange: DateRange
  efficiency: KPIPayload | null
  wipAging: KPIPayload | null
  onTimeDelivery: KPIPayload | null
  availability: KPIPayload | null
  performance: KPIPayload | null
  quality: KPIPayload | null
  oee: KPIPayload | null
  absenteeism: KPIPayload | null
  defectRates: KPIPayload | null
  throughputTime: KPIPayload | null
  inference: InferenceMap
  trends: TrendsMap
  predictions: PredictionsMap
  allPredictions: unknown | null
  benchmarks: unknown | null
  loading: boolean
  error: string | null
}

const defaultInference = (): InferenceData => ({
  is_estimated: false,
  confidence_score: 1.0,
  details: {},
})

const extractDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } } }
  return ax?.response?.data?.detail || fallback
}

export const useKPIStore = defineStore('kpi', {
  state: (): KPIState => ({
    dashboard: null,
    selectedClient: null,
    dateRange: {
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      end: new Date().toISOString().split('T')[0],
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
    inference: {
      efficiency: defaultInference(),
      wipAging: defaultInference(),
      onTimeDelivery: defaultInference(),
      availability: defaultInference(),
      performance: defaultInference(),
      quality: defaultInference(),
      oee: defaultInference(),
      absenteeism: defaultInference(),
      defectRates: defaultInference(),
      throughputTime: defaultInference(),
    },
    trends: {
      efficiency: [],
      wipAging: [],
      onTimeDelivery: [],
      availability: [],
      performance: [],
      quality: [],
      oee: [],
      absenteeism: [],
    },
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
      dpmo: null,
    },
    allPredictions: null,
    benchmarks: null,
    loading: false,
    error: null,
  }),

  getters: {
    kpiStatus:
      () =>
      (
        value: number | null | undefined,
        target: number | null | undefined,
        isHigherBetter = true,
      ): StatusColor => {
        if (!value || !target) return 'gray'
        const percentage = (value / target) * 100
        if (isHigherBetter) {
          if (percentage >= 95) return 'success'
          if (percentage >= 80) return 'warning'
          return 'error'
        }
        if (percentage <= 5) return 'success'
        if (percentage <= 20) return 'warning'
        return 'error'
      },

    kpiIcon:
      () =>
      (
        value: number | null | undefined,
        target: number | null | undefined,
        isHigherBetter = true,
      ): StatusIcon => {
        if (!value || !target) return 'mdi-minus-circle'
        const percentage = (value / target) * 100
        if (isHigherBetter) {
          if (percentage >= 95) return 'mdi-check-circle'
          if (percentage >= 80) return 'mdi-alert-circle'
          return 'mdi-close-circle'
        }
        if (percentage <= 5) return 'mdi-check-circle'
        if (percentage <= 20) return 'mdi-alert-circle'
        return 'mdi-close-circle'
      },

    allKPIs: (state): KPISummary[] => [
      {
        key: 'efficiency',
        title: 'Efficiency',
        value: state.efficiency?.current,
        target: state.efficiency?.target || 85,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-chart-line',
        route: '/kpi/efficiency',
        inference: state.inference.efficiency,
      },
      {
        key: 'wipAging',
        title: 'WIP Aging',
        value: state.wipAging?.average_days,
        target: 7,
        unit: 'days',
        higherBetter: false,
        icon: 'mdi-clock-alert',
        route: '/kpi/wip-aging',
        inference: state.inference.wipAging,
      },
      {
        key: 'onTimeDelivery',
        title: 'On-Time Delivery',
        value: state.onTimeDelivery?.percentage,
        target: 95,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-truck-delivery',
        route: '/kpi/on-time-delivery',
        inference: state.inference.onTimeDelivery,
      },
      {
        key: 'availability',
        title: 'Availability',
        value: state.availability?.percentage,
        target: 90,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-server',
        route: '/kpi/availability',
        inference: state.inference.availability,
      },
      {
        key: 'performance',
        title: 'Performance',
        value: state.performance?.percentage,
        target: 95,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-speedometer',
        route: '/kpi/performance',
        inference: state.inference.performance,
      },
      {
        key: 'quality',
        title: 'Quality (FPY)',
        value: state.quality?.fpy,
        target: 99,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-star-circle',
        route: '/kpi/quality',
        inference: state.inference.quality,
      },
      {
        key: 'oee',
        title: 'OEE',
        value: state.oee?.percentage,
        target: 85,
        unit: '%',
        higherBetter: true,
        icon: 'mdi-factory',
        route: '/kpi/oee',
        inference: state.inference.oee,
      },
      {
        key: 'absenteeism',
        title: 'Absenteeism',
        value: state.absenteeism?.rate,
        target: 5,
        unit: '%',
        higherBetter: false,
        icon: 'mdi-account-alert',
        route: '/kpi/absenteeism',
        inference: state.inference.absenteeism,
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
        subtitle:
          state.defectRates?.defect_rate_percentage != null
            ? `${state.defectRates.defect_rate_percentage}% defect rate`
            : null,
        inference: state.inference.defectRates,
      },
      {
        key: 'throughputTime',
        title: 'Throughput Time',
        value: state.throughputTime?.average_hours,
        target: 24,
        unit: 'hrs',
        higherBetter: false,
        icon: 'mdi-timer',
        route: '/kpi/efficiency',
        inference: state.inference.throughputTime,
      },
    ],

    hasAnyEstimatedKPIs: (state): boolean =>
      Object.values(state.inference).some((inf) => inf.is_estimated),

    overallDataQuality: (state): number => {
      const confidenceScores = Object.values(state.inference)
        .filter((inf) => inf.confidence_score !== undefined)
        .map((inf) => inf.confidence_score)

      if (confidenceScores.length === 0) return 1.0
      return confidenceScores.reduce((a, b) => a + b, 0) / confidenceScores.length
    },
  },

  actions: {
    setClient(clientId: string | number | null): void {
      this.selectedClient = clientId
    },

    setDateRange(start: string, end: string): void {
      this.dateRange = { start, end }
    },

    _buildParams(): Record<string, unknown> {
      const params: Record<string, unknown> = {
        start_date: this.dateRange.start,
        end_date: this.dateRange.end,
      }
      if (this.selectedClient) {
        params.client_id = this.selectedClient
      }
      return params
    },

    _updateInference(kpiKey: KPIKey, inferenceData: Partial<InferenceData> | null): void {
      if (!inferenceData) {
        this.inference[kpiKey] = defaultInference()
        return
      }

      this.inference[kpiKey] = {
        is_estimated: inferenceData.is_estimated || false,
        confidence_score: inferenceData.confidence_score || 1.0,
        details: {
          cycle_time: (inferenceData as KPIPayload).cycle_time || null,
          employees: (inferenceData as KPIPayload).employees || null,
          scheduled_hours: (inferenceData as KPIPayload).scheduled_hours || null,
        },
      }
    },

    _extractInferenceFromResponse(response: KPIPayload | null | undefined, kpiKey: KPIKey): void {
      if (response?.inference) {
        this._updateInference(kpiKey, response.inference)
        return
      }

      if (response?.was_inferred !== undefined) {
        this._updateInference(kpiKey, {
          is_estimated: response.was_inferred,
          confidence_score: response.was_inferred ? 0.7 : 1.0,
        })
        return
      }

      if (response?.has_estimated !== undefined) {
        this._updateInference(kpiKey, {
          is_estimated: response.has_estimated,
          confidence_score: response.data_quality || (response.has_estimated ? 0.7 : 1.0),
        })
        return
      }

      this._updateInference(kpiKey, null)
    },

    async fetchDashboard(): Promise<unknown | null> {
      this.loading = true
      this.error = null
      try {
        const params = this._buildParams()
        const response = await api.getKPIDashboard(params)
        this.dashboard = response.data
        return response.data
      } catch (error) {
        this.error = extractDetail(error, 'Failed to fetch dashboard')
        // eslint-disable-next-line no-console
        console.error('Dashboard fetch error:', error)
        useNotificationStore().showError(this.error)
        return null
      } finally {
        this.loading = false
      }
    },

    async _fetchKPI(
      kpi: KPIKey,
      stateField: KPIKey,
      dataLabel: string,
      fetchData: () => Promise<{ data: KPIPayload }>,
      fetchTrend: (() => Promise<{ data: unknown[] }>) | null = null,
      trendField: keyof TrendsMap | null = null,
    ): Promise<KPIPayload | null> {
      this.loading = true
      try {
        const promises: Promise<unknown>[] = [fetchData()]
        if (fetchTrend) promises.push(fetchTrend())

        const results = await Promise.all(promises)
        const dataRes = results[0] as { data: KPIPayload }
        const trendRes = results[1] as { data: unknown[] } | undefined

        ;(this as KPIState)[stateField] = dataRes.data

        if (trendField && trendRes) {
          this.trends[trendField] = trendRes.data || []
        }

        this._extractInferenceFromResponse(dataRes.data, kpi)
        return dataRes.data
      } catch (error) {
        this.error = extractDetail(error, `Failed to fetch ${dataLabel}`)
        // eslint-disable-next-line no-console
        console.error(`${dataLabel} fetch error:`, error)
        useNotificationStore().showError(this.error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchEfficiency() {
      const params = this._buildParams()
      return this._fetchKPI(
        'efficiency',
        'efficiency',
        'efficiency',
        () => api.getEfficiency(params),
        () => api.getEfficiencyTrend(params),
        'efficiency',
      )
    },

    async fetchWIPAging() {
      const params = this._buildParams()
      return this._fetchKPI(
        'wipAging',
        'wipAging',
        'WIP aging',
        () => api.getWIPAging(params),
        () => api.getWIPAgingTrend(params),
        'wipAging',
      )
    },

    async fetchOnTimeDelivery() {
      const params = this._buildParams()
      return this._fetchKPI(
        'onTimeDelivery',
        'onTimeDelivery',
        'on-time delivery',
        () => api.getOnTimeDelivery(params),
        () => api.getOnTimeDeliveryTrend(params),
        'onTimeDelivery',
      )
    },

    async fetchAvailability() {
      const params = this._buildParams()
      return this._fetchKPI(
        'availability',
        'availability',
        'availability',
        () => api.getAvailability(params),
        () => api.getAvailabilityTrend(params),
        'availability',
      )
    },

    async fetchPerformance() {
      const params = this._buildParams()
      return this._fetchKPI(
        'performance',
        'performance',
        'performance',
        () => api.getPerformance(params),
        () => api.getPerformanceTrend(params),
        'performance',
      )
    },

    async fetchQuality() {
      const params = this._buildParams()
      return this._fetchKPI(
        'quality',
        'quality',
        'quality',
        () => api.getQuality(params),
        () => api.getQualityTrend(params),
        'quality',
      )
    },

    async fetchOEE() {
      const params = this._buildParams()
      return this._fetchKPI(
        'oee',
        'oee',
        'OEE',
        () => api.getOEE(params),
        () => api.getOEETrend(params),
        'oee',
      )
    },

    async fetchAbsenteeism() {
      const params = this._buildParams()
      return this._fetchKPI(
        'absenteeism',
        'absenteeism',
        'absenteeism',
        () => api.getAbsenteeism(params),
        () => api.getAbsenteeismTrend(params),
        'absenteeism',
      )
    },

    async fetchDefectRates() {
      const params = this._buildParams()
      return this._fetchKPI(
        'defectRates',
        'defectRates',
        'defect rates',
        () => api.getDefectRates(params),
      )
    },

    async fetchThroughputTime() {
      const params = this._buildParams()
      return this._fetchKPI(
        'throughputTime',
        'throughputTime',
        'throughput time',
        () => api.getThroughputTime(params),
      )
    },

    async fetchAllKPIs(): Promise<void> {
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
          this.fetchThroughputTime(),
        ])
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error fetching all KPIs:', error)
      } finally {
        this.loading = false
      }
    },

    async fetchPrediction(
      kpiType: PredictionKey,
      forecastDays = 7,
      historicalDays = 30,
      method: ForecastMethod = 'auto',
    ): Promise<unknown | null> {
      this.loading = true
      try {
        const params = {
          ...this._buildParams(),
          forecast_days: forecastDays,
          historical_days: historicalDays,
          method: method,
        }
        // The JS version passed `kpiType` straight through; the
        // typed API surface only supports a narrower set, but
        // 'quality' was historically accepted at runtime — preserve
        // the previous behavior with an explicit cast.
        const response = await api.getPrediction(kpiType as 'efficiency', params)

        const stateKey = kpiType
        if (stateKey in this.predictions) {
          this.predictions[stateKey as keyof PredictionsMap] = response.data
        }
        return response.data
      } catch (error) {
        this.error = extractDetail(error, `Failed to fetch ${kpiType} prediction`)
        // eslint-disable-next-line no-console
        console.error(`Prediction fetch error for ${kpiType}:`, error)
        useNotificationStore().showError(this.error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchAllPredictions(forecastDays = 7, historicalDays = 30): Promise<unknown | null> {
      this.loading = true
      try {
        const params = {
          ...this._buildParams(),
          forecast_days: forecastDays,
          historical_days: historicalDays,
        }
        const response = await api.getAllPredictions(params)
        this.allPredictions = response.data

        if (response.data) {
          const data = response.data as Record<string, PredictionResponse | undefined>
          const kpiTypes: PredictionKey[] = [
            'efficiency',
            'performance',
            'availability',
            'oee',
            'ppm',
            'dpmo',
            'fpy',
            'rty',
            'absenteeism',
            'otd',
          ]
          kpiTypes.forEach((kpi) => {
            if (data[kpi]) {
              this.predictions[kpi] = data[kpi] as PredictionResponse
            }
          })
        }

        return response.data
      } catch (error) {
        this.error = extractDetail(error, 'Failed to fetch all predictions')
        // eslint-disable-next-line no-console
        console.error('All predictions fetch error:', error)
        useNotificationStore().showError(this.error)
        return null
      } finally {
        this.loading = false
      }
    },

    async fetchBenchmarks(): Promise<unknown | null> {
      try {
        const response = await api.getPredictionBenchmarks()
        this.benchmarks = response.data
        return response.data
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Benchmarks fetch error:', error)
        return null
      }
    },

    async fetchKPIHealth(kpiType: PredictionKey): Promise<unknown | null> {
      try {
        const params = this._buildParams()
        // Same behavioral preservation as fetchPrediction — the JS
        // version accepted 'quality' even though the backend's
        // KPIType union doesn't list it.
        const response = await api.getKPIHealth(kpiType as 'efficiency', params)
        return response.data
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(`Health fetch error for ${kpiType}:`, error)
        return null
      }
    },

    getForecastChartData(
      prediction: PredictionResponse | null,
      color = '#9c27b0',
    ): ChartData | null {
      if (!prediction || !prediction.predictions) {
        return null
      }

      const forecastLabels = prediction.predictions.map((p) => {
        const date = new Date(p.date)
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      })

      const forecastValues = prediction.predictions.map((p) => p.predicted_value)
      const lowerBounds = prediction.predictions.map((p) => p.lower_bound)
      const upperBounds = prediction.predictions.map((p) => p.upper_bound)

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
            pointRadius: 4,
          },
          {
            label: 'Confidence Upper',
            data: upperBounds,
            borderColor: `${color}50`,
            backgroundColor: `${color}10`,
            borderDash: [2, 2],
            tension: 0.3,
            fill: '+1',
            pointRadius: 0,
          },
          {
            label: 'Confidence Lower',
            data: lowerBounds,
            borderColor: `${color}50`,
            backgroundColor: 'transparent',
            borderDash: [2, 2],
            tension: 0.3,
            fill: false,
            pointRadius: 0,
          },
        ],
      }
    },
  },
})
