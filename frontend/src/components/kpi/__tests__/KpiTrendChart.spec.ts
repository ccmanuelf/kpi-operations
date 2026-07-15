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

  it('recomputes OOC when the threshold arrives after cold-load, without a redundant fetch', async () => {
    const fetchTrend = vi.fn().mockResolvedValue([
      { date: '2026-06-10', value: 90 },
      { date: '2026-06-11', value: 40 },
    ])
    // Mirrors the real dashboard: the parent mounts this chart with
    // threshold=null and fills it in once its own async load resolves.
    const w = mount(KpiTrendChart, {
      props: {
        metricKey: 'efficiency',
        title: 'Efficiency',
        threshold: null,
        clientId: 'C',
        unit: '%',
        fetchTrend,
        alertKey: null,
      },
      global: { plugins: [i18n, createVuetify()] },
    })
    await flushPromises()
    expect(fetchTrend).toHaveBeenCalledTimes(1)

    let lineData: any = w.findComponent({ name: 'Line' }).props('data')
    // No threshold yet -> critical arm can't flag anything.
    expect(lineData.datasets[0].pointRadius).toEqual([3, 3])

    await w.setProps({ threshold: { critical: 60, higher_is_better: true } })
    await flushPromises()

    // Threshold-only change must NOT trigger another network fetch.
    expect(fetchTrend).toHaveBeenCalledTimes(1)

    lineData = w.findComponent({ name: 'Line' }).props('data')
    expect(lineData.datasets[0].pointRadius).toEqual([3, 7])
  })

  it('styles the out-of-control point distinctly in the main dataset', async () => {
    const fetchTrend = vi.fn().mockResolvedValue([
      { date: '2026-06-10', value: 90 },
      { date: '2026-06-11', value: 40 }, // below critical=60, higher-is-better -> OOC
      { date: '2026-06-12', value: 88 },
    ])
    const w = mountChart(fetchTrend, { critical: 60, higher_is_better: true })
    await flushPromises()

    const lineData: any = w.findComponent({ name: 'Line' }).props('data')
    const main = lineData.datasets[0]

    // Enlarged radius and thicker border at the OOC index only.
    expect(main.pointRadius).toEqual([3, 7, 3])
    expect(main.pointBorderWidth).toEqual([1, 3, 1])
    // Border color at the OOC index is distinct from the normal points.
    expect(main.pointBorderColor[1]).not.toBe(main.pointBorderColor[0])
    expect(main.pointBorderColor[1]).not.toBe(main.pointBorderColor[2])
    expect(main.pointBorderColor[0]).toBe(main.pointBorderColor[2])
  })

  it('discards a stale out-of-order fetch response (latest range wins)', async () => {
    let resolveFirst: (_v: unknown) => void = () => {}
    const first = new Promise((r) => {
      resolveFirst = r
    })
    const fetchTrend = vi
      .fn()
      .mockReturnValueOnce(first) // mount fetch — resolves LATE (stale)
      .mockResolvedValueOnce([{ date: '2026-06-20', value: 55 }]) // range-change fetch — resolves first (latest)
    const w = mountChart(fetchTrend)
    // Trigger a second load (range change) while the mount fetch is still pending.
    ;(w.vm as { onRangeChange: (_k: string) => void }).onRangeChange('lastWeek')
    await flushPromises() // the latest (second) fetch resolves and applies
    // Now the stale first fetch resolves — the guard must discard it.
    resolveFirst([{ date: '2026-01-01', value: 99 }])
    await flushPromises()

    const lineData: string = JSON.stringify(w.findComponent({ name: 'Line' }).props('data'))
    // The chart must reflect the latest (second) response value 55, not the stale 99.
    expect(lineData).toContain('55')
    expect(lineData).not.toContain('99')
  })
})
