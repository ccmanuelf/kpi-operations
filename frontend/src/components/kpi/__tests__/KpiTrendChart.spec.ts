import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import KpiTrendChart from '../KpiTrendChart.vue'

// stub the Line chart so we can assert the data it receives without a canvas
vi.mock('vue-chartjs', () => ({ Line: { name: 'Line', props: ['data', 'options'], template: '<div class="line-stub" />' } }))

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: {
  kpi: { thisWeek: 'This Week', lastWeek: 'Last Week', lastMonth: 'Last Month', last90Days: 'Last 90 Days',
         outOfControl: 'Out of control', target: 'Target', criticalLine: 'Critical', controlLimit: 'Control limit',
         ooc: { belowCritical: '{value} below {critical}', aboveCritical: '{value} above {critical}',
                beyondUcl: '{value} > {limit}', beyondLcl: '{value} < {limit}' } } } } })

const mountChart = (fetchTrend: any, threshold: any = { critical: 60, higher_is_better: true }) =>
  mount(KpiTrendChart, {
    props: { metricKey: 'efficiency', title: 'Efficiency', threshold, clientId: 'C', unit: '%', fetchTrend, alertKey: null },
    global: { plugins: [i18n, createVuetify()] },
  })

describe('KpiTrendChart', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches its trend on mount and renders the Line', async () => {
    const fetchTrend = vi.fn().mockResolvedValue([{ date: '2026-06-10', value: 90 }, { date: '2026-06-11', value: 88 }])
    const w = mountChart(fetchTrend)
    await flushPromises()
    expect(fetchTrend).toHaveBeenCalledTimes(1)
    expect(w.find('.line-stub').exists()).toBe(true)
  })

  it('refetches when the range selector changes', async () => {
    const fetchTrend = vi.fn().mockResolvedValue([])
    const w = mountChart(fetchTrend)
    await flushPromises()
    // simulate range change through the component's exposed handler
    ;(w.vm as any).onRangeChange?.('lastWeek')
    await flushPromises()
    expect(fetchTrend.mock.calls.length).toBeGreaterThanOrEqual(2)
    // second call carries a different start/end than the first
    expect(fetchTrend.mock.calls[1][0].start_date).not.toBe(fetchTrend.mock.calls[0][0].start_date)
  })
})
