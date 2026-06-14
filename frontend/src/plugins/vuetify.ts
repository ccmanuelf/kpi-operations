import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import { md3 } from 'vuetify/blueprints/md3'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'
import { buildMd3Theme } from '@/theme/md3Tonal'

// MD3 tonal role tokens are now derived from the Carbon brand seeds
// (see src/theme/carbonSeeds.ts + md3Tonal.ts), replacing the previous
// hardcoded Carbon color maps. WCAG-AA verified in Task 2.

export default createVuetify({
  blueprint: md3,
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        ...buildMd3Theme('light'),
        variables: {
          'border-radius-root': '4px',
          'high-emphasis-opacity': 0.87,
          'medium-emphasis-opacity': 0.6,
          'disabled-opacity': 0.38,
          'hover-opacity': 0.04,
          'activated-opacity': 0.12,
          'pressed-opacity': 0.16,
          'focus-opacity': 0.12,
          'selected-opacity': 0.08,
        },
      },
      dark: {
        ...buildMd3Theme('dark'),
        variables: {
          'border-radius-root': '4px',
          'high-emphasis-opacity': 0.87,
          'medium-emphasis-opacity': 0.6,
          'disabled-opacity': 0.38,
          'hover-opacity': 0.08,
          'activated-opacity': 0.16,
          'pressed-opacity': 0.2,
          'focus-opacity': 0.16,
          'selected-opacity': 0.12,
        },
      },
    },
  },
  defaults: {
    VCard: { elevation: 0, rounded: 'lg', border: true },
    VBtn: { rounded: 'md', elevation: 0 },
    VTextField: { variant: 'outlined', density: 'compact' },
    VSelect: { variant: 'outlined', density: 'compact' },
    VAutocomplete: { variant: 'outlined', density: 'compact' },
    VCombobox: { variant: 'outlined', density: 'compact' },
    VTextarea: { variant: 'outlined', density: 'comfortable' },
    VCheckbox: { color: 'primary' },
    VRadio: { color: 'primary' },
    VSwitch: { color: 'primary', inset: true },
    VChip: { rounded: 'lg' },
    VAlert: { rounded: 'md', border: 'start', variant: 'tonal' },
    // The JS version had duplicate VSnackbar and VDialog keys; the
    // second occurrence won, so the `rounded` values were silently
    // dropped. Preserving runtime behavior — only the surviving
    // attributes are kept here.
    VSnackbar: { timeout: 4000, location: 'bottom' },
    VDataTable: { hover: true, density: 'compact' },
    VList: { rounded: 'md' },
    VListItem: { rounded: 'md' },
    VMenu: { rounded: 'md' },
    VDialog: { transition: 'dialog-transition' },
    VProgressLinear: { rounded: true },
    VProgressCircular: { width: 3 },
    VTabs: { color: 'primary' },
    VTab: { rounded: 'md' },
    VTooltip: { location: 'bottom' },
    VSkeletonLoader: { boilerplate: false },
  },
})
