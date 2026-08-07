import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import { setActivePinia, createPinia } from 'pinia'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

vi.mock('@/services/api/client', () => ({ default: { get: vi.fn().mockResolvedValue({ data: { rows: [], totals: {} } }) } }))

// Heavy/child-composable-backed leaves — their own behavior is covered by
// AGGridBase's and useWIPAgingData's own specs; this view spec only asserts
// PivotSummaries' own structure (tab count, bucket selector, download button).
vi.mock('@/components/grids/AGGridBase.vue', () => ({
  default: { template: '<div class="ag-grid-base-stub" />' },
}))
vi.mock('@/components/WipTriadBlock.vue', () => ({
  default: { template: '<div class="wip-triad-stub" />' },
}))

import { VALID_BUCKETS } from '@/composables/pivotPresets'
import PivotSummaries from '@/views/PivotSummaries.vue'

// Mirrors the vuetify + i18n + pinia harness used by other view specs
// (frontend/src/views/__tests__/NotFoundView.spec.ts for the plugin pair,
// frontend/src/views/__tests__/admin-views.spec.ts for setActivePinia).
const mountView = () => {
  setActivePinia(createPinia())
  return mount(PivotSummaries, {
    global: {
      plugins: [createI18n({ legacy: false, locale: 'en', messages: { en, es } }), createVuetify()],
    },
  })
}

describe('PivotSummaries', () => {
  it('renders five tabs, one per management question', () => {
    const wrapper = mountView()
    expect(wrapper.findAll('[data-testid^="pivot-tab-"]')).toHaveLength(5)
  })

  it('renders bucket selector offering exactly the four VALID_BUCKETS options, plus a download button', () => {
    const wrapper = mountView()
    const bucketSelect = wrapper.findComponent('[data-testid="pivot-bucket-select"]')
    expect(bucketSelect.exists()).toBe(true)
    const items = bucketSelect.props('items') as Array<{ value: string; title: string }>
    expect(items).toHaveLength(4)
    expect(items.map((i) => i.value).sort()).toEqual([...VALID_BUCKETS].sort())
    expect(wrapper.find('[data-testid="pivot-download"]').exists()).toBe(true)
  })
})
