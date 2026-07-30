import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import NotFoundView from '../NotFoundView.vue'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

const mountView = (locale: 'en' | 'es' = 'en') =>
  mount(NotFoundView, {
    global: {
      plugins: [createI18n({ legacy: false, locale, messages: { en, es } }), createVuetify()],
    },
  })

describe('NotFoundView (ISSUE 015)', () => {
  it('renders the localized title and description in English', () => {
    const w = mountView('en')
    expect(w.text()).toContain(en.notFound.title)
    expect(w.text()).toContain(en.notFound.description)
  })

  it('renders the localized title in Spanish', () => {
    const w = mountView('es')
    expect(w.text()).toContain(es.notFound.title)
  })

  it('navigates home when the action button is triggered', async () => {
    const w = mountView('en')
    await w.findComponent({ name: 'EmptyState' }).vm.$emit('action')
    expect(push).toHaveBeenCalledWith('/')
  })
})
