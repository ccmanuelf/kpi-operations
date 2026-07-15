import { describe, it, expect } from 'vitest'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'
import { KPI_CHART_CONFIG } from '../kpiChartConfig'

const REAL = new Set(['quality', 'availability', 'oee', 'wipAging', 'otd', 'absenteeism', 'ppm'])
const CAUSE_KINDS = ['downtime', 'defect', 'absence', 'lateOrders', 'hold', 'component']

describe('SP2 cause config + i18n', () => {
  it('flags exactly the seven real-driver metrics as causeDriven', () => {
    for (const cfg of KPI_CHART_CONFIG) {
      expect(cfg.causeDriven).toBe(REAL.has(cfg.metricKey))
    }
  })

  it('defines every kpi.cause.<kind> key in both locales', () => {
    for (const kind of CAUSE_KINDS) {
      expect((en as any).kpi.cause[kind], `en kpi.cause.${kind}`).toBeTruthy()
      expect((es as any).kpi.cause[kind], `es kpi.cause.${kind}`).toBeTruthy()
    }
  })
})
