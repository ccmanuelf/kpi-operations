/**
 * Lazy Chart Loading Composable
 *
 * Provides lazy-loaded Chart.js components to reduce initial bundle size.
 * Chart.js (~250KB) is only loaded when charts are actually needed.
 *
 * @example
 * // In a component:
 * const { LineChart, BarChart, loading, error } = useLazyCharts()
 *
 * // In template:
 * <component :is="LineChart" v-if="!loading" :data="chartData" :options="options" />
 */

import { ref, shallowRef, markRaw } from 'vue'

// Module-level cache for loaded chart components
let chartModulesCache = null
let loadPromise = null

/**
 * Load Chart.js and vue-chartjs modules
 */
async function loadChartModules() {
  // Return cached modules if already loaded
  if (chartModulesCache) {
    return chartModulesCache
  }

  // Return existing promise if load is in progress
  if (loadPromise) {
    return loadPromise
  }

  // Start loading
  loadPromise = (async () => {
    try {
      // Dynamic imports for code splitting
      const [chartjs, vueChartjs] = await Promise.all([
        import('chart.js'),
        import('vue-chartjs')
      ])

      // Register Chart.js components
      chartjs.Chart.register(
        chartjs.CategoryScale,
        chartjs.LinearScale,
        chartjs.PointElement,
        chartjs.LineElement,
        chartjs.BarElement,
        chartjs.ArcElement,
        chartjs.Title,
        chartjs.Tooltip,
        chartjs.Legend,
        chartjs.Filler
      )

      // Cache the modules
      chartModulesCache = {
        Line: markRaw(vueChartjs.Line),
        Bar: markRaw(vueChartjs.Bar),
        Pie: markRaw(vueChartjs.Pie),
        Doughnut: markRaw(vueChartjs.Doughnut),
        Radar: markRaw(vueChartjs.Radar),
        PolarArea: markRaw(vueChartjs.PolarArea),
        Bubble: markRaw(vueChartjs.Bubble),
        Scatter: markRaw(vueChartjs.Scatter),
        ChartJS: chartjs.Chart
      }

      return chartModulesCache
    } catch (error) {
      // Reset promise on error to allow retry
      loadPromise = null
      throw error
    }
  })()

  return loadPromise
}

/**
 * Composable for lazy loading chart components
 *
 * @returns {Object} Chart components and loading state
 */
export function useLazyCharts() {
  const loading = ref(true)
  const error = ref(null)

  // Use shallowRef for components to avoid deep reactivity overhead
  const LineChart = shallowRef(null)
  const BarChart = shallowRef(null)
  const PieChart = shallowRef(null)
  const DoughnutChart = shallowRef(null)
  const RadarChart = shallowRef(null)
  const PolarAreaChart = shallowRef(null)
  const BubbleChart = shallowRef(null)
  const ScatterChart = shallowRef(null)

  // Load charts immediately
  loadChartModules()
    .then(modules => {
      LineChart.value = modules.Line
      BarChart.value = modules.Bar
      PieChart.value = modules.Pie
      DoughnutChart.value = modules.Doughnut
      RadarChart.value = modules.Radar
      PolarAreaChart.value = modules.PolarArea
      BubbleChart.value = modules.Bubble
      ScatterChart.value = modules.Scatter
      loading.value = false
    })
    .catch(err => {
      console.error('[useLazyCharts] Failed to load Chart.js:', err)
      error.value = err
      loading.value = false
    })

  return {
    loading,
    error,
    LineChart,
    BarChart,
    PieChart,
    DoughnutChart,
    RadarChart,
    PolarAreaChart,
    BubbleChart,
    ScatterChart
  }
}

/**
 * Preload chart modules in the background
 * Call this when user is likely to view charts soon
 *
 * @example
 * // Preload when user hovers over dashboard link
 * onMouseEnter: () => preloadCharts()
 */
export function preloadCharts() {
  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(() => {
      loadChartModules().catch(() => {
        // Silent fail for preload
      })
    })
  } else {
    setTimeout(() => {
      loadChartModules().catch(() => {
        // Silent fail for preload
      })
    }, 100)
  }
}

/**
 * Check if charts are already loaded
 */
export function areChartsLoaded() {
  return chartModulesCache !== null
}

/**
 * Default chart options optimized for performance
 */
export const defaultChartOptions = {
  responsive: true,
  maintainAspectRatio: true,

  // Disable animations on mobile for better performance
  animation: {
    duration: window.matchMedia('(max-width: 768px)').matches ? 0 : 400
  },

  // Optimize for large datasets
  parsing: {
    xAxisKey: 'x',
    yAxisKey: 'y'
  },

  // Reduce render overhead
  elements: {
    point: {
      radius: 3,
      hoverRadius: 5
    },
    line: {
      tension: 0.3
    }
  },

  // Plugin configuration
  plugins: {
    legend: {
      display: true,
      position: 'top',
      labels: {
        usePointStyle: true,
        padding: 15
      }
    },
    tooltip: {
      mode: 'index',
      intersect: false,
      // Use external tooltip on mobile for better UX
      enabled: true
    }
  },

  // Interaction optimization
  interaction: {
    mode: 'nearest',
    axis: 'x',
    intersect: false
  },

  // Scale optimization
  scales: {
    y: {
      beginAtZero: true,
      ticks: {
        maxTicksLimit: 8 // Reduce ticks for cleaner look
      }
    },
    x: {
      ticks: {
        maxTicksLimit: 12,
        maxRotation: 45
      }
    }
  }
}

/**
 * Create chart options with KPI-specific defaults
 *
 * @param {Object} overrides - Options to merge with defaults
 * @returns {Object} Merged chart options
 */
export function createKPIChartOptions(overrides = {}) {
  return {
    ...defaultChartOptions,
    ...overrides,
    plugins: {
      ...defaultChartOptions.plugins,
      ...overrides.plugins
    },
    scales: {
      ...defaultChartOptions.scales,
      ...overrides.scales,
      y: {
        ...defaultChartOptions.scales.y,
        ...overrides.scales?.y,
        max: 100, // KPIs are typically percentages
        ticks: {
          ...defaultChartOptions.scales.y.ticks,
          ...overrides.scales?.y?.ticks,
          callback: (value) => `${value}%`
        }
      }
    }
  }
}

export default useLazyCharts
