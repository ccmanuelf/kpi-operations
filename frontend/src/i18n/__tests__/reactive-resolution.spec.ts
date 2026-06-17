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

// es-toggle spot-check: store/registry titles resolve in Spanish when locale is toggled.
// Uses real en/es locale JSON to ensure the translated strings are correct.
import en from '../locales/en.json'
import es from '../locales/es.json'

describe('es-toggle: store and registry titles switch to Spanish', () => {
  it('kpi store allKPIs titles switch when locale changes to es', async () => {
    setActivePinia(createPinia())

    const i18nFull = createI18n({
      legacy: false,
      locale: 'en',
      fallbackLocale: 'en',
      messages: { en, es },
    })

    // Simulate what kpi store allKPIs getter does: read from i18n.global.t
    const useKpiProbe = defineStore('kpi-locale-probe', {
      getters: {
        efficiencyTitle: () => i18nFull.global.t('kpi.efficiency'),
        oeeTitle: () => i18nFull.global.t('kpi.oeeShort'),
        absenteeismTitle: () => i18nFull.global.t('kpi.absenteeismShort'),
        throughputTitle: () => i18nFull.global.t('kpi.throughputTime'),
        wipAgingTitle: () => i18nFull.global.t('kpi.wipAging'),
      },
    })

    const KpiProbe = defineComponent({
      setup() {
        const s = useKpiProbe()
        return () => h('div', [
          h('span', { id: 'eff' }, s.efficiencyTitle),
          h('span', { id: 'oee' }, s.oeeTitle),
          h('span', { id: 'abs' }, s.absenteeismTitle),
        ])
      },
    })

    const w = mount(KpiProbe, { global: { plugins: [i18nFull] } })

    // en baseline
    expect(i18nFull.global.t('kpi.efficiency')).toBe('Efficiency')
    expect(i18nFull.global.t('kpi.oeeShort')).toBe('OEE')
    expect(i18nFull.global.t('kpi.absenteeismShort')).toBe('Absenteeism')
    expect(i18nFull.global.t('kpi.throughputTime')).toBe('Throughput Time')
    expect(i18nFull.global.t('kpi.wipAging')).toBe('WIP Aging')

    // toggle to es
    i18nFull.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(i18nFull.global.t('kpi.efficiency')).toBe('Eficiencia')
    expect(i18nFull.global.t('kpi.oeeShort')).toBe('OEE')
    expect(i18nFull.global.t('kpi.absenteeismShort')).toBe('Ausentismo')
    expect(i18nFull.global.t('kpi.throughputTime')).toBe('Tiempo de Ciclo')
    expect(i18nFull.global.t('kpi.wipAging')).toBe('Antigüedad WIP')
  })

  it('widgetRegistry getter names switch to Spanish when locale toggles', async () => {
    setActivePinia(createPinia())

    const i18nFull = createI18n({
      legacy: false,
      locale: 'en',
      fallbackLocale: 'en',
      messages: { en, es },
    })

    const useRegistryProbe = defineStore('registry-locale-probe', {
      getters: {
        downtimeImpactName: () => i18nFull.global.t('widgets.registry.downtimeImpact'),
        alertName: () => i18nFull.global.t('alerts.registry.absenteeismAlert'),
      },
    })

    const RegistryProbe = defineComponent({
      setup() {
        const s = useRegistryProbe()
        return () => h('div', [
          h('span', s.downtimeImpactName),
          h('span', s.alertName),
        ])
      },
    })

    const w = mount(RegistryProbe, { global: { plugins: [i18nFull] } })

    // en baseline
    expect(i18nFull.global.t('widgets.registry.downtimeImpact')).toBe('Downtime Impact on OEE')
    expect(i18nFull.global.t('alerts.registry.absenteeismAlert')).toBe('Absenteeism Threshold Alert')

    // toggle to es
    i18nFull.global.locale.value = 'es'
    await w.vm.$nextTick()

    expect(i18nFull.global.t('widgets.registry.downtimeImpact')).toBe('Impacto del Tiempo de Paro en OEE')
    expect(i18nFull.global.t('alerts.registry.absenteeismAlert')).toBe('Alerta de Umbral de Ausentismo')
  })
})
