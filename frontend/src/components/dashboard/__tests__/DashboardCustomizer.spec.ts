/**
 * Unit tests for DashboardCustomizer available-widget localization (C1b fix).
 *
 * Verifies that:
 *  1. Available-widget names render from dashboard.widgets.<key> in English.
 *  2. Available-widget descriptions render from dashboard.widgetDescriptions.<key> in English.
 *  3. Both name and description switch reactively to Spanish on locale toggle.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'
import DashboardCustomizer from '../DashboardCustomizer.vue'

const MOCK_ALL_WIDGETS = {
  my_kpis: { name: 'My KPIs', description: 'Your assigned client KPIs', icon: 'mdi-chart-box', minRole: 'operator' },
  qr_scanner: { name: 'QR Scanner', description: 'Scan QR codes for quick data entry', icon: 'mdi-qrcode-scan', minRole: 'operator' },
}

vi.mock('@/stores/dashboardStore', () => ({
  useDashboardStore: () => ({
    ALL_WIDGETS: MOCK_ALL_WIDGETS,
    layout: 'grid',
    widgets: [],
    userRole: 'operator',
    availableWidgets: [
      { widget_key: 'my_kpis', ...MOCK_ALL_WIDGETS.my_kpis },
      { widget_key: 'qr_scanner', ...MOCK_ALL_WIDGETS.qr_scanner },
    ],
    setLayout: vi.fn(),
    saveToAPI: vi.fn().mockResolvedValue(undefined),
    resetToDefaults: vi.fn(),
  }),
}))

vi.mock('vuedraggable', () => ({
  default: {
    name: 'draggable',
    template: '<div><slot name="item" v-for="(item, i) in modelValue" :key="i" :element="item" /></div>',
    props: ['modelValue', 'itemKey', 'handle', 'ghostClass', 'disabled', 'animation'],
    emits: ['update:modelValue', 'end'],
  },
}))

const extraStubs = {
  'v-dialog': { template: '<div class="v-dialog"><slot /></div>' },
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-card-actions': { template: '<div class="v-card-actions"><slot /></div>' },
  'v-btn': { template: '<button class="v-btn"><slot /></button>' },
  'v-btn-toggle': { template: '<div class="v-btn-toggle"><slot /></div>' },
  'v-icon': { template: '<span class="v-icon"><slot /></span>' },
  'v-spacer': { template: '<span class="v-spacer" />' },
  'v-chip': { template: '<span class="v-chip"><slot /></span>' },
  'v-list': { template: '<ul class="v-list"><slot /></ul>' },
  'v-list-item': {
    template: '<li class="v-list-item"><slot name="prepend" /><slot /><slot name="append" /></li>',
    emits: ['click'],
  },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-tooltip': { template: '<span class="v-tooltip"><slot /></span>' },
  'v-overlay': { template: '<div class="v-overlay" />' },
  'v-progress-circular': { template: '<div class="v-progress-circular" />' },
}

function makeI18n(locale = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { en, es },
  })
}

function mountCustomizer(i18n: ReturnType<typeof makeI18n>) {
  return mount(DashboardCustomizer, {
    props: { modelValue: true },
    global: { plugins: [i18n], stubs: extraStubs },
  })
}

describe('DashboardCustomizer – available-widget name + description localization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the localized English name for an available widget', () => {
    const i18n = makeI18n('en')
    const wrapper = mountCustomizer(i18n)
    // dashboard.widgets.my_kpis in en.json = "My KPIs"
    expect(wrapper.text()).toContain('My KPIs')
  })

  it('renders the localized English description for an available widget', () => {
    const i18n = makeI18n('en')
    const wrapper = mountCustomizer(i18n)
    // dashboard.widgetDescriptions.my_kpis in en.json
    expect(wrapper.text()).toContain('Your assigned client KPIs')
  })

  it('switches available-widget name and description reactively to Spanish on locale toggle', async () => {
    const i18n = makeI18n('en')
    const wrapper = mountCustomizer(i18n)

    // en baseline
    expect(wrapper.text()).toContain('My KPIs')
    expect(wrapper.text()).toContain('Your assigned client KPIs')

    // switch to es
    i18n.global.locale.value = 'es'
    await wrapper.vm.$nextTick()

    // dashboard.widgets.my_kpis in es.json = "Mis KPIs"
    expect(wrapper.text()).toContain('Mis KPIs')
    // dashboard.widgetDescriptions.my_kpis in es.json
    expect(wrapper.text()).toContain('Tus KPIs de clientes asignados')
  })
})
