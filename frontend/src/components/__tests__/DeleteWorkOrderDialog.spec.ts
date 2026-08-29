/**
 * The refused-delete dialog, rendered for real.
 *
 * Before this existed, the only coverage of the blocked-by list was
 * `smokeMount(WorkOrderManagement).exists()` — a shallowMount that never renders
 * the dialog body. The entire list could be deleted with the whole suite green.
 * Extracting the dialog from the `<script setup>` view is what makes its refused
 * state reachable from a spec at all.
 *
 * Vuetify teleports overlay content to document.body, so assertions read
 * document.body.textContent rather than the wrapper.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import DeleteWorkOrderDialog from '@/components/DeleteWorkOrderDialog.vue'
import type { BlockedByRow } from '@/services/api/structuredErrors'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const BLOCKERS: BlockedByRow[] = [
  { table: 'PRODUCTION_ENTRY', count: 4, label: 'Production entries' },
  { table: 'JOB', count: 1, label: 'Job' },
]

const render = (props: Record<string, unknown>, locale: 'en' | 'es' = 'en') =>
  mount(DeleteWorkOrderDialog, {
    props: { modelValue: true, workOrderId: 'WO-0002', ...props },
    global: {
      plugins: [
        createI18n({ legacy: false, locale, fallbackLocale: 'en', messages: { en, es } }),
        createVuetify(),
      ],
    },
    attachTo: document.body,
  })

const screen = () => document.body.textContent || ''

describe('DeleteWorkOrderDialog', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  describe('when the delete was refused', () => {
    it('lists every blocking entity with its count', async () => {
      render({ blockers: BLOCKERS })
      await new Promise((r) => setTimeout(r, 0))
      // Deleting the <ul> from the template fails both of these.
      expect(screen()).toContain('Production entries (4)')
      expect(screen()).toContain('Job (1)')
    })

    it('says the delete was refused instead of asking for confirmation', async () => {
      render({ blockers: BLOCKERS })
      await new Promise((r) => setTimeout(r, 0))
      expect(screen()).toContain(en.errors.deleteBlockedTitle)
      expect(screen()).toContain(en.errors.deleteBlockedIntro)
      expect(screen()).toContain(en.errors.deleteBlockedRemedy)
      // The confirmation copy must be gone: left beside the blocker list it
      // reads as though those records would be deleted along with the order.
      expect(screen()).not.toContain(en.grids.deleteConfirm)
      expect(screen()).not.toContain(en.common.confirmDelete)
    })

    it('withdraws the Delete action, which could only repeat the same refusal', async () => {
      const w = render({ blockers: BLOCKERS })
      await new Promise((r) => setTimeout(r, 0))
      // Asserted on the buttons, not on screen text: the remedy line legitimately
      // begins with the word "Delete", so a substring check on the body would be
      // testing the copy rather than the action.
      const labels = w.findAll('button').map((b) => b.text().trim())
      expect(labels).toEqual([en.common.close])
    })

    it('renders the whole refusal in Spanish under the es locale', async () => {
      render({ blockers: [{ table: 'PRODUCTION_ENTRY', count: 4, label: 'Registros de producción' }] }, 'es')
      await new Promise((r) => setTimeout(r, 0))
      expect(screen()).toContain(es.errors.deleteBlockedTitle)
      expect(screen()).toContain(es.errors.deleteBlockedIntro)
      expect(screen()).toContain('Registros de producción (4)')
      expect(screen()).not.toContain(en.errors.deleteBlockedTitle)
    })

    it('marks the list up as a list, so it renders with bullets', async () => {
      const w = render({ blockers: BLOCKERS })
      await new Promise((r) => setTimeout(r, 0))
      // Tailwind's preflight strips ul markers app-wide; the component restates
      // list-style, and this asserts the markup it applies to still exists.
      const list = document.body.querySelector('ul.blocked-by-list')
      expect(list).not.toBeNull()
      expect(list?.querySelectorAll('li')).toHaveLength(2)
      expect(w.html()).toContain('blocked-by-list')
    })
  })

  describe('when nothing blocks the delete', () => {
    it('asks for confirmation and names the work order', async () => {
      render({ blockers: [] })
      await new Promise((r) => setTimeout(r, 0))
      expect(screen()).toContain(en.common.confirmDelete)
      expect(screen()).toContain('WO-0002')
      expect(screen()).not.toContain(en.errors.deleteBlockedIntro)
      expect(document.body.querySelector('ul.blocked-by-list')).toBeNull()
    })

    it('offers Delete, and emits confirm when it is pressed', async () => {
      const w = render({ blockers: [] })
      await new Promise((r) => setTimeout(r, 0))
      const buttons = w.findAll('button')
      expect(buttons).toHaveLength(2)
      await buttons[1].trigger('click')
      expect(w.emitted('confirm')).toBeTruthy()
    })

    it('closes without confirming when Cancel is pressed', async () => {
      const w = render({ blockers: [] })
      await new Promise((r) => setTimeout(r, 0))
      await w.findAll('button')[0].trigger('click')
      expect(w.emitted('update:modelValue')?.[0]).toEqual([false])
      expect(w.emitted('confirm')).toBeFalsy()
    })
  })
})
