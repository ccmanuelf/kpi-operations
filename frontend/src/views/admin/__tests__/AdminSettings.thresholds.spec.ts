/**
 * Focused regression test for the Admin Settings "KPI Thresholds" panel.
 *
 * Root cause of the e2e-sweep observation ("ALL fields render as empty
 * placeholders"): the prod-safe demo seeder never created any
 * client_id=NULL KPIThreshold row, so GET /api/kpi-thresholds (no
 * client_id) returned `{ thresholds: {} }` for the panel's default view —
 * a load-path/data problem, not a frontend binding bug. That fix lived in
 * backend/scripts/_seed_reference.py, which S1c deleted along with the rest
 * of the old seeder — and backend.seed does NOT write global rows, so the
 * empty default view is currently back. Recorded as gap 2 in
 * docs/superpowers/specs/2026-08-21-seeder-cutover-s1c-design.md section 2.1.
 * This test asserts the DISPLAY
 * side of the contract: when the API *does* return threshold rows, the
 * panel's fields render those values instead of staying blank.
 *
 * AdminSettings.vue is a plain (non-TS) `<script setup>` SFC, so its
 * internal `thresholds` ref isn't reachable via wrapper.vm — this asserts
 * the rendered DOM instead. The threshold fields are the only
 * `type="number"` inputs in the view, so that's a stable, unique selector.
 * The project-wide `v-text-field` stub (src/test/setup.ts) renders a bare
 * `<input class="v-text-field" />` with no bound attributes, so it's
 * overridden locally here to actually reflect `type`/`modelValue` into the
 * DOM — every other test file's global stub is left untouched.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getKPIThresholds: vi.fn(() =>
      Promise.resolve({
        data: {
          client_id: null,
          client_name: null,
          thresholds: {
            efficiency: { target_value: 85, is_global: true },
            quality: { target_value: 99, is_global: true },
            availability: { target_value: 90, is_global: true },
            performance: { target_value: 95, is_global: true },
            oee: { target_value: 85, is_global: true },
            ppm: { target_value: 500, is_global: true },
            absenteeism: { target_value: 5, is_global: true },
            otd: { target_value: 95, is_global: true },
            wip_aging: { target_value: 7, is_global: true },
            throughput: { target_value: 24, is_global: true },
          },
        },
      }),
    ),
    updateKPIThresholds: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))
vi.mock('@/services/api', () => ({ default: apiMock }))

import AdminSettings from '../AdminSettings.vue'

describe('AdminSettings — KPI Thresholds panel', () => {
  it('renders fetched threshold values instead of blank placeholders', async () => {
    const wrapper = mount(AdminSettings, {
      global: {
        stubs: {
          'v-text-field': {
            template: '<input class="v-text-field" :type="type" :value="modelValue" />',
            props: ['modelValue', 'type'],
          },
        },
      },
    })
    await flushPromises()

    expect(apiMock.getKPIThresholds).toHaveBeenCalled()

    const numberInputs = wrapper.findAll('input[type="number"]')
    // One field per kpiList entry.
    expect(numberInputs.length).toBe(10)
    // First entry is efficiency (kpiList order) — must show the fetched
    // 85, not be empty.
    expect((numberInputs[0].element as HTMLInputElement).value).toBe('85')
    // Fields must not ALL be blank (the reported regression).
    const values = numberInputs.map((w) => (w.element as HTMLInputElement).value)
    expect(values.every((v) => v === '')).toBe(false)
  })
})
