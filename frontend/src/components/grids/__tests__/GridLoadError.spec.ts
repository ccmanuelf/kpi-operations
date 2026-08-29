/**
 * The banner that explains an empty grid.
 *
 * The load-failure state carries three meanings and the component must keep
 * them apart: null (healthy, render nothing), a message (failed, show it), and
 * the empty string (failed with no detail — still show the banner). Collapsing
 * the last two would restore exactly the silence this replaces.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import GridLoadError from '../GridLoadError.vue'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const render = (props: Record<string, unknown>, locale: 'en' | 'es' = 'en') =>
  mount(GridLoadError, {
    props,
    global: {
      plugins: [
        createI18n({ legacy: false, locale, fallbackLocale: 'en', messages: { en, es } }),
        createVuetify(),
      ],
    },
  })

describe('GridLoadError', () => {
  it('renders nothing when the load is healthy', () => {
    const w = render({ message: null })
    expect(w.text()).toBe('')
    expect(w.find('[role="alert"]').exists()).toBe(false)
  })

  it('explains the failure and shows the backend reason', () => {
    const w = render({ message: 'Failed to fetch entries' })
    expect(w.text()).toContain(en.grids.loadFailed)
    expect(w.text()).toContain('Failed to fetch entries')
    expect(w.find('[role="alert"]').exists()).toBe(true)
  })

  it('still appears when the failure carried no message', () => {
    // '' is falsy but not null. If this rendered nothing, a failed load with no
    // detail would leave an unexplained empty grid — the original bug.
    const w = render({ message: '' })
    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(w.text()).toContain(en.grids.loadFailed)
  })

  it('offers a retry and emits it', async () => {
    const w = render({ message: 'down' })
    const button = w.find('button')
    expect(button.text()).toContain(en.grids.loadFailedRetry)
    await button.trigger('click')
    expect(w.emitted('retry')).toBeTruthy()
  })

  it('renders in Spanish under the es locale', () => {
    const w = render({ message: 'algo falló' }, 'es')
    expect(w.text()).toContain(es.grids.loadFailed)
    expect(w.text()).toContain(es.grids.loadFailedRetry)
    expect(w.text()).not.toContain(en.grids.loadFailed)
  })
})
