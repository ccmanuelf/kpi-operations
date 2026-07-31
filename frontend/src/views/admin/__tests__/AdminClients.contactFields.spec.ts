/**
 * Focused regression tests for the Admin Clients screen's field bindings
 * (e2e-sweep coordinator follow-up on the Task 10 seeder work).
 *
 * Part 1 root cause: AdminClients.vue read/wrote contact_name/contact_email/
 * contact_phone, but the backend's Client schema (backend/schemas/client.py
 * ClientCreate/ClientUpdate/ClientResponse), ORM (backend/orm/client.py),
 * and the CLIENTS CSV upload/export (backend/endpoints/csv_upload.py) all
 * use client_contact/client_email/client_phone consistently — there is no
 * aliasing anywhere on the backend side. The frontend was the wrong side;
 * fixed to bind the real field names instead.
 *
 * Part 2 root cause (no-tech-debt follow-up): the form additionally
 * read/wrote industry/address/notes, none of which exist anywhere on the
 * backend's Client schema/ORM — a reviewer confirmed this silently drops
 * whatever an admin typed into those fields (the save still "succeeds"
 * because Pydantic just ignores unknown fields), which is a real defect,
 * not a cosmetic one. Removed those three; added the backend's real
 * `location: Optional[str]` field (backend/schemas/client.py) in their
 * place.
 *
 * The project-wide `v-data-table` stub (src/test/setup.ts) only renders a
 * bare `<table><slot /></table>` with no iteration over `items`/`headers`
 * and no scoped-slot rendering; `v-form`/`v-text-field` aren't wired for
 * two-way v-model either — so all three are overridden locally here
 * (matching the pattern already used in AdminSettings.thresholds.spec.ts
 * for `v-text-field`). Every other test file's global stub is left
 * untouched.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'

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
            location: 'Monterrey, MX',
            is_active: 1,
            created_at: '2026-06-15T00:00:00Z',
          },
        ],
      }),
    ),
    createClient: vi.fn(() => Promise.resolve({ data: {} })),
    updateClient: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k, locale: { value: 'en' } }),
}))
vi.mock('@/services/api', () => ({ default: apiMock }))

import AdminClients from '../AdminClients.vue'

// Renders every column via `item[header.key]` (Vuetify's real default cell
// behavior) plus the `item.actions` scoped slot (the row's view/edit/
// toggle/delete icon buttons), which the base stub renders neither of.
const dataTableStub = {
  props: ['headers', 'items', 'loading', 'search', 'noDataText'],
  template: `
    <table class="v-data-table">
      <tr v-for="item in items" :key="item.client_id" class="data-row">
        <td v-for="h in headers" :key="h.key" :data-key="h.key">{{ item[h.key] }}</td>
        <slot name="item.actions" :item="item" />
      </tr>
    </table>
  `,
}

// Real Vuetify validation isn't loaded in this stubbed environment, so
// `formValid` (bound to the submit button's `:disabled`) would otherwise
// never flip true; mark the form valid as soon as it mounts.
const formStub = {
  props: ['modelValue'],
  emits: ['update:modelValue'],
  mounted() {
    this.$emit('update:modelValue', true)
  },
  template: '<form class="v-form"><slot /></form>',
}

// Reflects `label` into a `data-label` attribute (a stable selector, since
// none of these fields carry an id/name) and wires a real v-model.
const textFieldStub = {
  props: ['modelValue', 'label', 'type', 'disabled', 'rules'],
  emits: ['update:modelValue'],
  template:
    '<input class="v-text-field" :data-label="label" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

function findButtonByText(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button.v-btn').find((b) => b.text().includes(text))
}

function findButtonByIcon(wrapper: VueWrapper, icon: string) {
  return wrapper
    .findAll('button.v-btn')
    .find((b) => b.find('.v-icon').exists() && b.find('.v-icon').text() === icon)
}

describe('AdminClients — contact field binding', () => {
  it("renders a client's client_contact/client_email using the backend's real field names", async () => {
    const wrapper = mount(AdminClients, {
      global: { stubs: { 'v-data-table': dataTableStub } },
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
    // The industry column was removed along with the phantom
    // industry/address/notes fields — must never reappear.
    expect(wrapper.find('td[data-key="industry"]').exists()).toBe(false)
  })
})

describe('AdminClients — form submits only real backend schema fields', () => {
  it('create: the payload has no industry/address/notes keys, and location round-trips', async () => {
    const wrapper = mount(AdminClients, {
      global: { stubs: { 'v-data-table': dataTableStub, 'v-form': formStub, 'v-text-field': textFieldStub } },
    })
    await flushPromises()

    const addBtn = findButtonByText(wrapper, 'admin.clients.addClient')
    expect(addBtn).toBeDefined()
    await addBtn!.trigger('click')
    await flushPromises()

    await wrapper.find('input[data-label="admin.clients.clientId"]').setValue('DEMO-NEW')
    await wrapper.find('input[data-label="admin.clients.clientName"]').setValue('New Demo Client')
    await wrapper.find('input[data-label="admin.clients.location"]').setValue('Austin, US')

    const createBtn = findButtonByText(wrapper, 'admin.clients.createClient')
    expect(createBtn).toBeDefined()
    await createBtn!.trigger('click')
    await flushPromises()

    expect(apiMock.createClient).toHaveBeenCalledTimes(1)
    const payload = apiMock.createClient.mock.calls[0][0] as Record<string, unknown>
    expect(Object.keys(payload).sort()).toEqual(
      ['client_contact', 'client_email', 'client_id', 'client_name', 'client_phone', 'location'].sort(),
    )
    expect(payload).not.toHaveProperty('industry')
    expect(payload).not.toHaveProperty('address')
    expect(payload).not.toHaveProperty('notes')
    expect(payload.client_id).toBe('DEMO-NEW')
    expect(payload.location).toBe('Austin, US')
  })

  it('edit: location renders a fetched value and round-trips on update, with no phantom fields', async () => {
    const wrapper = mount(AdminClients, {
      global: { stubs: { 'v-data-table': dataTableStub, 'v-form': formStub, 'v-text-field': textFieldStub } },
    })
    await flushPromises()

    const editBtn = findButtonByIcon(wrapper, 'mdi-pencil')
    expect(editBtn).toBeDefined()
    await editBtn!.trigger('click')
    await flushPromises()

    const locationInput = wrapper.find('input[data-label="admin.clients.location"]')
    expect((locationInput.element as HTMLInputElement).value).toBe('Monterrey, MX')

    const updateBtn = findButtonByText(wrapper, 'common.update')
    expect(updateBtn).toBeDefined()
    await updateBtn!.trigger('click')
    await flushPromises()

    expect(apiMock.updateClient).toHaveBeenCalledTimes(1)
    const [clientId, payload] = apiMock.updateClient.mock.calls[0] as [string, Record<string, unknown>]
    expect(clientId).toBe('DEMO-PIECE')
    expect(Object.keys(payload).sort()).toEqual(
      ['client_contact', 'client_email', 'client_id', 'client_name', 'client_phone', 'location'].sort(),
    )
    expect(payload.location).toBe('Monterrey, MX')
    expect(payload).not.toHaveProperty('industry')
    expect(payload).not.toHaveProperty('address')
    expect(payload).not.toHaveProperty('notes')
  })
})
