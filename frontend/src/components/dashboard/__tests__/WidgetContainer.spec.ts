/**
 * Unit tests for WidgetContainer render-site localization (C1b fix).
 *
 * Verifies that:
 *  1. Known widget_keys are localized via dashboard.widgets.<key> (en + es toggle).
 *  2. Unknown/custom widget_keys fall back to the persisted widget_name.
 *  3. The localized title is reactive — switching locale updates the rendered text.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

// Mock the dashboardStore so the component can mount without a real store
vi.mock('@/stores/dashboardStore', () => ({
  useDashboardStore: () => ({
    ALL_WIDGETS: {
      my_kpis: { icon: 'mdi-chart-bar' },
      qr_scanner: { icon: 'mdi-qrcode-scan' },
    },
  }),
}))

import WidgetContainer from '../WidgetContainer.vue'

// Additional stubs beyond those in src/test/setup.ts
const extraStubs = {
  'v-divider': { template: '<hr class="v-divider" />' },
  'v-card-actions': { template: '<div class="v-card-actions"><slot /></div>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-menu': { template: '<div class="v-menu"><slot /><slot name="activator" /></div>' },
  'v-tooltip': { template: '<span class="v-tooltip"><slot /></span>' },
}

function makeI18n(locale = 'en') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { en, es },
  })
}

describe('WidgetContainer – widget title localization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the localized en title for a known widget_key', () => {
    const i18n = makeI18n('en')
    const wrapper = mount(WidgetContainer, {
      props: { widget: { widget_key: 'my_kpis', widget_name: 'My KPIs' } },
      global: { plugins: [i18n], stubs: extraStubs },
    })
    // dashboard.widgets.my_kpis in en.json = "My KPIs"
    expect(wrapper.text()).toContain('My KPIs')
  })

  it('renders the Spanish title after locale is toggled to es', async () => {
    const i18n = makeI18n('en')
    const wrapper = mount(WidgetContainer, {
      props: { widget: { widget_key: 'my_kpis', widget_name: 'My KPIs' } },
      global: { plugins: [i18n], stubs: extraStubs },
    })
    // en baseline
    expect(wrapper.text()).toContain('My KPIs')

    // switch to es — dashboard.widgets.my_kpis in es.json = "Mis KPIs"
    i18n.global.locale.value = 'es'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Mis KPIs')
  })

  it('falls back to persisted widget_name for an unknown widget_key', () => {
    const i18n = makeI18n('en')
    const wrapper = mount(WidgetContainer, {
      props: {
        widget: {
          widget_key: 'custom_widget_xyz',
          widget_name: 'My Custom Widget',
        },
      },
      global: { plugins: [i18n], stubs: extraStubs },
    })
    // No dashboard.widgets.custom_widget_xyz key exists → falls back to persisted name
    expect(wrapper.text()).toContain('My Custom Widget')
  })

  it('renders the localized title in the edit-mode preview slot', async () => {
    const i18n = makeI18n('en')
    const wrapper = mount(WidgetContainer, {
      props: {
        widget: { widget_key: 'qr_scanner', widget_name: 'QR Scanner' },
        isEditing: true,
      },
      global: { plugins: [i18n], stubs: extraStubs },
    })
    // dashboard.widgets.qr_scanner in en.json = "QR Scanner"
    expect(wrapper.text()).toContain('QR Scanner')

    // switch to es — "Escáner QR"
    i18n.global.locale.value = 'es'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Escáner QR')
  })
})
