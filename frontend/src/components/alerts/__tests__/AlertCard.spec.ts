/**
 * Focused regression test for AlertCard's relative-time formatting
 * (e2e-sweep live-VM residual: alerts rendered "-296m ago").
 *
 * Root cause: created_at is stored naive-UTC (no timezone designator).
 * `new Date(str)` parses a timezone-less string as LOCAL time, not UTC —
 * for any viewer not in UTC, `created` silently shifts by the viewer's UTC
 * offset, which can put it "in the future" relative to `now` and render a
 * negative duration. Fixed by explicitly forcing UTC interpretation
 * (appending 'Z' when the string has no timezone designator) and clamping
 * any still-possible tiny future skew (clock drift, in-flight latency) to
 * "just now" instead of a negative number.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))

import AlertCard from '../AlertCard.vue'

const baseAlert = {
  alert_id: 'A1',
  severity: 'info',
  status: 'active',
  category: 'trend',
  title: 'Test Alert',
  message: 'Test message',
  recommendation: null,
  current_value: null,
  threshold_value: null,
  predicted_value: null,
  confidence: null,
  created_at: '2026-07-31T12:00:00',
}

// Fixed "now" so relative-time math is deterministic.
const NOW = new Date('2026-07-31T12:00:00Z')

describe('AlertCard — relative time (UTC-naive timestamps)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a positive "Xm ago" for a naive-UTC timestamp 5 minutes in the past', () => {
    const wrapper = mount(AlertCard, {
      props: { alert: { ...baseAlert, created_at: '2026-07-31T11:55:00' } },
    })
    expect(wrapper.find('.timestamp').text()).toBe('5m ago')
  })

  it('clamps a slightly-future naive-UTC timestamp to "just now" instead of a negative duration', () => {
    const wrapper = mount(AlertCard, {
      props: { alert: { ...baseAlert, created_at: '2026-07-31T12:00:03' } },
    })
    const text = wrapper.find('.timestamp').text()
    expect(text).toBe('alerts.justNow')
    expect(text).not.toMatch(/^-/)
  })

  it('still handles an explicit-UTC ("Z"-suffixed) timestamp correctly', () => {
    const wrapper = mount(AlertCard, {
      props: { alert: { ...baseAlert, created_at: '2026-07-31T11:50:00Z' } },
    })
    expect(wrapper.find('.timestamp').text()).toBe('10m ago')
  })
})
