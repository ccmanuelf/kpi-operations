/**
 * The scenario comparison table, rendered against the shape the API ACTUALLY
 * sends.
 *
 * It previously read `results.scenarios[]`, each carrying a nested `results`
 * object — a shape `POST /api/capacity/scenarios/compare` has never returned.
 * The route answers with a bare ARRAY of comparison rows, so
 * `results.scenarios?.length` was always undefined, the table's `v-if` was
 * always false, and the dialog opened empty. Nothing caught it: the store and
 * service specs mock `{ scenarios: [], metrics: [] }`, so they asserted the
 * mock rather than the contract and stayed green while the feature was dead.
 *
 * These fixtures are copied from a live capture of the route against a seeded
 * database, so a future divergence fails here.
 *
 * Vuetify teleports overlay content to document.body, so assertions read
 * document.body.textContent rather than the wrapper.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import ScenarioCompareDialog from '../ScenarioCompareDialog.vue'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

/** Exactly the field set the route returns, numbers not strings. */
const comparison = (over: Record<string, unknown> = {}) => ({
  scenario_id: 1,
  scenario_name: 'Overtime: +20% on every line',
  scenario_type: 'OVERTIME',
  original_capacity_hours: 1000,
  modified_capacity_hours: 1200,
  capacity_increase_percent: 20,
  original_utilization: 82.5,
  modified_utilization: 68.75,
  bottlenecks_resolved: 2,
  cost_impact: 3000,
  notes: 'Saved plan',
  ...over,
})

const render = (results: unknown, locale: 'en' | 'es' = 'en') =>
  mount(ScenarioCompareDialog, {
    props: { modelValue: true, results },
    global: {
      plugins: [
        createI18n({ legacy: false, locale, fallbackLocale: 'en', messages: { en, es } }),
        createVuetify(),
      ],
    },
    attachTo: document.body,
  })

const screen = () => document.body.textContent || ''

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ScenarioCompareDialog', () => {
  it('renders a column per scenario from the array the API returns', () => {
    render([
      comparison(),
      comparison({
        scenario_id: 2,
        scenario_name: 'Changeover: cut setup time 30%',
        scenario_type: 'SETUP_REDUCTION',
      }),
    ])
    expect(screen()).toContain('Overtime: +20% on every line')
    expect(screen()).toContain('Changeover: cut setup time 30%')
    expect(screen()).toContain('OVERTIME')
    expect(screen()).toContain('SETUP_REDUCTION')
  })

  it('formats each metric in its own unit', () => {
    render([comparison()])
    const text = screen()
    expect(text).toContain('1,200') // capacity hours, thousands separated
    expect(text).toContain('20.0%') // capacity increase, one decimal
    expect(text).toContain('68.8%') // utilisation, rounded to one decimal
    expect(text).toContain('$3,000') // cost impact, currency
    expect(text).toContain('2') // bottlenecks resolved, plain count
  })

  it('shows the empty state when there is nothing to compare', () => {
    render(null)
    expect(screen()).toContain('No comparison results available.')
  })

  it('shows the empty state for the OLD nested shape rather than half-rendering', () => {
    // `{scenarios: [...]}` is what the dialog used to expect. If the API ever
    // regresses to it, the dialog must say it has nothing rather than render a
    // table of blanks that reads as "all metrics are N/A".
    render({ scenarios: [{ id: 1, name: 'x', results: { avg_utilization: 50 } }] } as unknown)
    expect(screen()).toContain('No comparison results available.')
  })

  it('marks the winner only when the scenarios actually differ', () => {
    // Two plans, different capacity gains -> the better one is highlighted.
    const differing = render([
      comparison({ scenario_id: 1, capacity_increase_percent: 20 }),
      comparison({ scenario_id: 2, capacity_increase_percent: 5 }),
    ])
    expect(document.body.querySelectorAll('.text-success').length).toBeGreaterThan(0)
    differing.unmount()
    document.body.innerHTML = ''

    // An unseeded capacity module makes every plan report 0. Highlighting a
    // "winner" there would claim one plan beat another when nothing separated
    // them.
    render([
      comparison({ scenario_id: 1, capacity_increase_percent: 0, cost_impact: 0 }),
      comparison({ scenario_id: 2, capacity_increase_percent: 0, cost_impact: 0 }),
    ])
    expect(document.body.querySelectorAll('.text-success').length).toBe(0)
  })

  it('localises the metric labels', () => {
    render([comparison()], 'es')
    expect(screen()).toContain('Aumento de Capacidad')
  })
})
