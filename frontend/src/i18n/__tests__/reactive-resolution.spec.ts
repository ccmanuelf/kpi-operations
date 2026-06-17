import { describe, it, expect } from 'vitest'
import { setActivePinia, createPinia, defineStore } from 'pinia'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { defineComponent, h } from 'vue'

const i18n = createI18n({
  legacy: false, globalInjection: true, locale: 'en', fallbackLocale: 'en',
  messages: { en: { kpi: { efficiency: 'Efficiency' } }, es: { kpi: { efficiency: 'Eficiencia' } } },
})

describe('reactive i18n.global.t inside a Pinia getter', () => {
  it('getter re-resolves when the locale changes', async () => {
    setActivePinia(createPinia())
    const useStore = defineStore('probe', {
      getters: { label: () => i18n.global.t('kpi.efficiency') },
    })
    const Probe = defineComponent({ setup() { const s = useStore(); return () => h('span', s.label) } })
    const w = mount(Probe, { global: { plugins: [i18n] } })
    expect(w.text()).toBe('Efficiency')
    i18n.global.locale.value = 'es'
    await w.vm.$nextTick()
    expect(w.text()).toBe('Eficiencia')
  })
})
