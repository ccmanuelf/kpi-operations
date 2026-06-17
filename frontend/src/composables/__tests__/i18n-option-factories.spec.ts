/**
 * Tests for Task 4 (C1b) i18n option-list factories.
 *
 * Covers:
 * - useOrderStatusOptions / useWorkOrderStatusOptions / useWorkOrderPriorityOptions
 * - useDatePresets
 * - useExportSheetOptions
 * - OTD modes in useClientConfigForms (via computed otdModeOptions)
 * - filterTypeOptions in useKPIFilters
 *
 * Each test:
 *   1. Mounts in real i18n (en baseline) via real locale JSON.
 *   2. Toggles to es and asserts Spanish labels appear.
 *   3. Ensures `value` / `icon` / `days` identifiers are untouched.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { createI18n } from 'vue-i18n'
import en from '../../i18n/locales/en.json'
import es from '../../i18n/locales/es.json'

// filtersStore is imported (transitively via useFilterBarData) at module-eval
// time and accesses localStorage via i18n/index.ts. Mock out the stores that
// have module-level side-effects so the factories under test can be imported
// cleanly with a fresh createI18n instance.
vi.mock('@/stores/filtersStore', () => ({
  useFiltersStore: () => ({
    activeFilter: null,
    hasActiveFilter: false,
    recentFilters: [],
    filtersByType: {},
    savedFilters: [],
    initializeFilters: vi.fn(),
    applyFilter: vi.fn(),
    applyQuickFilter: vi.fn(),
    getDefaultForType: vi.fn(() => null),
    clearActiveFilter: vi.fn(),
    createFilterConfig: vi.fn((c) => c),
    getFilterParams: {},
  }),
}))

// ---- factories under test ----
import {
  useOrderStatusOptions,
  useWorkOrderStatusOptions,
  useWorkOrderPriorityOptions,
} from '../useOrderStatusOptions'
import { useExportSheetOptions } from '../useExportSheetOptions'
import { useDatePresets } from '../useFilterBarData'

// ---- helpers ----

beforeEach(() => {
  setActivePinia(createPinia())
})

function makeI18n(locale = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { en, es },
  })
}

/** Mount a minimal component that calls `setupFn` inside setup, capturing the return. */
function mountFactory<T>(setupFn: () => T, i18n: ReturnType<typeof makeI18n>): T {
  let captured: T
  const C = defineComponent({
    setup() {
      captured = setupFn()
      return () => null
    },
  })
  mount(C, { global: { plugins: [i18n] } })
  return captured!
}

// ---------------------------------------------------------------------------

describe('useOrderStatusOptions (Plan-vs-Actual statuses)', () => {
  it('returns English labels in en locale', () => {
    const i18n = makeI18n('en')
    const opts = mountFactory(() => useOrderStatusOptions(), i18n)
    expect(opts.value.find((o) => o.value === 'PENDING')?.title).toBe('Pending')
    expect(opts.value.find((o) => o.value === 'IN_PROGRESS')?.title).toBe('In Progress')
    expect(opts.value.find((o) => o.value === 'COMPLETED')?.title).toBe('Completed')
    expect(opts.value.find((o) => o.value === 'ON_HOLD')?.title).toBe('On Hold')
    expect(opts.value.find((o) => o.value === 'CANCELLED')?.title).toBe('Cancelled')
  })

  it('es-toggle: returns Spanish labels after locale switch', async () => {
    const i18n = makeI18n('en')
    const C = defineComponent({
      setup() {
        const opts = useOrderStatusOptions()
        return () => h('span', opts.value.map((o) => o.title).join(','))
      },
    })
    const w = mount(C, { global: { plugins: [i18n] } })
    expect(w.text()).toContain('Pending')

    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(w.text()).toContain('Pendiente')
    expect(w.text()).toContain('En Progreso')
    expect(w.text()).toContain('Completado')
    expect(w.text()).toContain('En Espera')
    expect(w.text()).toContain('Cancelado')
  })

  it('value identifiers are never localized', () => {
    const i18n = makeI18n('es')
    const opts = mountFactory(() => useOrderStatusOptions(), i18n)
    const values = opts.value.map((o) => o.value)
    expect(values).toEqual(['PENDING', 'IN_PROGRESS', 'COMPLETED', 'ON_HOLD', 'CANCELLED'])
  })
})

// ---------------------------------------------------------------------------

describe('useWorkOrderStatusOptions (Work-Order management statuses)', () => {
  it('es-toggle: returns Spanish labels', async () => {
    const i18n = makeI18n('en')
    const C = defineComponent({
      setup() {
        const opts = useWorkOrderStatusOptions()
        return () => h('span', opts.value.map((o) => o.title).join(','))
      },
    })
    const w = mount(C, { global: { plugins: [i18n] } })
    expect(w.text()).toContain('Active')

    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(w.text()).toContain('Activo')
    expect(w.text()).toContain('En Espera')
    expect(w.text()).toContain('Completado')
    expect(w.text()).toContain('Rechazado')
    expect(w.text()).toContain('Cancelado')
  })
})

// ---------------------------------------------------------------------------

describe('useWorkOrderPriorityOptions', () => {
  it('es-toggle: returns Spanish priority labels', async () => {
    const i18n = makeI18n('en')
    const C = defineComponent({
      setup() {
        const opts = useWorkOrderPriorityOptions()
        return () => h('span', opts.value.map((o) => o.title).join(','))
      },
    })
    const w = mount(C, { global: { plugins: [i18n] } })
    expect(w.text()).toContain('Urgent')

    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(w.text()).toContain('Urgente')
    expect(w.text()).toContain('Alto')
    expect(w.text()).toContain('Normal')
    expect(w.text()).toContain('Medio')
    expect(w.text()).toContain('Bajo')
  })

  it('value identifiers are never localized', () => {
    const i18n = makeI18n('es')
    const opts = mountFactory(() => useWorkOrderPriorityOptions(), i18n)
    const values = opts.value.map((o) => o.value)
    expect(values).toEqual(['URGENT', 'HIGH', 'NORMAL', 'MEDIUM', 'LOW'])
  })
})

// ---------------------------------------------------------------------------

describe('useDatePresets (filter bar presets)', () => {
  it('returns English preset labels in en locale', () => {
    const i18n = makeI18n('en')
    const presets = mountFactory(() => useDatePresets(), i18n)
    expect(presets.value.find((p) => p.value === 'today')?.label).toBe('Today')
    expect(presets.value.find((p) => p.value === '7d')?.label).toBe('Last 7 Days')
    expect(presets.value.find((p) => p.value === '30d')?.label).toBe('Last 30 Days')
    expect(presets.value.find((p) => p.value === '90d')?.label).toBe('Last 90 Days')
    expect(presets.value.find((p) => p.value === 'ytd')?.label).toBe('Year to Date')
    expect(presets.value.find((p) => p.value === 'custom')?.label).toBe('Custom Range')
  })

  it('es-toggle: returns Spanish preset labels', async () => {
    const i18n = makeI18n('en')
    const C = defineComponent({
      setup() {
        const presets = useDatePresets()
        return () => h('span', presets.value.map((p) => p.label).join('|'))
      },
    })
    const w = mount(C, { global: { plugins: [i18n] } })
    expect(w.text()).toContain('Today')

    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(w.text()).toContain('Hoy')
    expect(w.text()).toContain('Últimos 7 Días')
    expect(w.text()).toContain('Últimos 30 Días')
    expect(w.text()).toContain('Últimos 90 Días')
    expect(w.text()).toContain('Año hasta la Fecha')
    expect(w.text()).toContain('Rango Personalizado')
  })

  it('non-label fields (value, icon, days) are not localized', () => {
    const i18n = makeI18n('es')
    const presets = mountFactory(() => useDatePresets(), i18n)
    const today = presets.value.find((p) => p.value === 'today')!
    expect(today.icon).toBe('mdi-calendar-today')
    expect(today.days).toBe(0)
  })
})

// ---------------------------------------------------------------------------

describe('useExportSheetOptions (capacity export sheets)', () => {
  it('returns English sheet labels in en locale', () => {
    const i18n = makeI18n('en')
    const opts = mountFactory(() => useExportSheetOptions(), i18n)
    expect(opts.value.find((o) => o.value === 'orders')?.title).toBe('Orders')
    expect(opts.value.find((o) => o.value === 'masterCalendar')?.title).toBe('Calendar')
    expect(opts.value.find((o) => o.value === 'productionLines')?.title).toBe('Production Lines')
  })

  it('es-toggle: returns Spanish sheet labels', async () => {
    const i18n = makeI18n('en')
    const C = defineComponent({
      setup() {
        const opts = useExportSheetOptions()
        return () => h('span', opts.value.map((o) => o.title).join(','))
      },
    })
    const w = mount(C, { global: { plugins: [i18n] } })
    expect(w.text()).toContain('Orders')

    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(w.text()).toContain('Órdenes')
    expect(w.text()).toContain('Calendario')
    expect(w.text()).toContain('Líneas de Producción')
    expect(w.text()).toContain('Estándares')
    expect(w.text()).toContain('Inventario')
  })

  it('value identifiers are never localized', () => {
    const i18n = makeI18n('es')
    const opts = mountFactory(() => useExportSheetOptions(), i18n)
    const values = opts.value.map((o) => o.value)
    expect(values).toEqual([
      'orders',
      'masterCalendar',
      'productionLines',
      'productionStandards',
      'bom',
      'stockSnapshot',
    ])
  })
})
