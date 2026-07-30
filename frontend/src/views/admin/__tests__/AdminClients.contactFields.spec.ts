/**
 * Focused regression test for the Admin Clients screen's contact-field
 * binding (e2e-sweep coordinator follow-up on the Task 10 seeder work).
 *
 * Root cause: AdminClients.vue read/wrote contact_name/contact_email/
 * contact_phone, but the backend's Client schema (backend/schemas/client.py
 * ClientCreate/ClientUpdate/ClientResponse), ORM (backend/orm/client.py),
 * and the CLIENTS CSV upload/export (backend/endpoints/csv_upload.py) all
 * use client_contact/client_email/client_phone consistently — there is no
 * aliasing anywhere on the backend side. The frontend was the wrong side;
 * fixed to bind the real field names instead. This test asserts the
 * DISPLAY side of the contract: the clients table renders a client's
 * contact values from a mocked GET /clients response using those exact
 * field names, and never keys off the old (nonexistent-on-the-backend)
 * names.
 *
 * The project-wide `v-data-table` stub (src/test/setup.ts) only renders a
 * bare `<table><slot /></table>` with no iteration over `items`/`headers`
 * (AdminClients.vue's data table uses column-key binding, not scoped
 * per-column slots, for the contact columns) — so it's overridden locally
 * here to emulate Vuetify's actual default cell rendering
 * (`item[header.key]` per column), matching the pattern already used in
 * AdminSettings.thresholds.spec.ts for `v-text-field`. Every other test
 * file's global stub is left untouched.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    getClients: vi.fn(() =>
      Promise.resolve({
        data: [
          {
            client_id: 'DEMO-PIECE',
            client_name: 'Demo Piece-Rate Garments',
            client_contact: 'Maria Torres',
            client_email: 'maria.torres@demopiece.example',
            client_phone: '+1-555-0101',
            is_active: 1,
            created_at: '2026-06-15T00:00:00Z',
          },
        ],
      }),
    ),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))
vi.mock('@/services/api', () => ({ default: apiMock }))

import AdminClients from '../AdminClients.vue'

describe('AdminClients — contact field binding', () => {
  it("renders a client's client_contact/client_email using the backend's real field names", async () => {
    const wrapper = mount(AdminClients, {
      global: {
        stubs: {
          'v-data-table': {
            props: ['headers', 'items', 'loading', 'search', 'noDataText'],
            template: `
              <table class="v-data-table">
                <tr v-for="item in items" :key="item.client_id" class="data-row">
                  <td v-for="h in headers" :key="h.key" :data-key="h.key">{{ item[h.key] }}</td>
                </tr>
              </table>
            `,
          },
        },
      },
    })
    await flushPromises()

    expect(apiMock.getClients).toHaveBeenCalled()

    const contactCell = wrapper.find('td[data-key="client_contact"]')
    const emailCell = wrapper.find('td[data-key="client_email"]')
    expect(contactCell.exists()).toBe(true)
    expect(emailCell.exists()).toBe(true)
    expect(contactCell.text()).toBe('Maria Torres')
    expect(emailCell.text()).toBe('maria.torres@demopiece.example')

    // Locks in the fix, not just the presence of the right keys: the old,
    // nonexistent-on-the-backend column keys must never appear.
    expect(wrapper.find('td[data-key="contact_name"]').exists()).toBe(false)
    expect(wrapper.find('td[data-key="contact_email"]').exists()).toBe(false)
  })
})
