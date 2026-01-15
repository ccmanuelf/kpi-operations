/**
 * Vuetify Configuration with IBM Carbon Design System Integration
 *
 * This configuration applies Carbon Design principles while using Vuetify components.
 * Colors, typography, and spacing follow Carbon Design System v11 guidelines.
 */
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

// IBM Carbon-inspired color palette
const carbonColors = {
  // Primary - IBM Blue
  primary: '#0f62fe',
  'primary-darken-1': '#0043ce',
  'primary-darken-2': '#002d9c',
  'primary-lighten-1': '#4589ff',
  'primary-lighten-2': '#78a9ff',

  // Secondary - Cool Gray
  secondary: '#393939',
  'secondary-darken-1': '#262626',
  'secondary-lighten-1': '#525252',

  // Success - Green
  success: '#198038',
  'success-darken-1': '#0e6027',
  'success-lighten-1': '#24a148',
  'success-lighten-2': '#42be65',

  // Warning - Yellow
  warning: '#f1c21b',
  'warning-darken-1': '#b28600',
  'warning-lighten-1': '#fddc69',

  // Error/Danger - Red
  error: '#da1e28',
  'error-darken-1': '#a2191f',
  'error-lighten-1': '#fa4d56',
  'error-lighten-2': '#ff8389',

  // Info - Teal
  info: '#0072c3',
  'info-darken-1': '#005d5d',
  'info-lighten-1': '#009d9a',

  // Surface colors
  surface: '#ffffff',
  'surface-variant': '#f4f4f4',
  'surface-bright': '#ffffff',

  // Background
  background: '#f4f4f4',

  // Text colors
  'on-surface': '#161616',
  'on-background': '#161616',
  'on-primary': '#ffffff',
  'on-secondary': '#ffffff',
  'on-success': '#ffffff',
  'on-warning': '#161616',
  'on-error': '#ffffff',
  'on-info': '#ffffff',
}

// Dark theme Carbon colors
const carbonDarkColors = {
  primary: '#78a9ff',
  'primary-darken-1': '#4589ff',
  'primary-lighten-1': '#a6c8ff',

  secondary: '#c6c6c6',
  'secondary-darken-1': '#a8a8a8',
  'secondary-lighten-1': '#e0e0e0',

  success: '#42be65',
  'success-darken-1': '#24a148',
  'success-lighten-1': '#6fdc8c',

  warning: '#f1c21b',
  'warning-darken-1': '#d2a106',
  'warning-lighten-1': '#fddc69',

  error: '#ff8389',
  'error-darken-1': '#fa4d56',
  'error-lighten-1': '#ffb3b8',

  info: '#3ddbd9',
  'info-darken-1': '#08bdba',
  'info-lighten-1': '#9ef0f0',

  surface: '#262626',
  'surface-variant': '#393939',
  'surface-bright': '#525252',

  background: '#161616',

  'on-surface': '#f4f4f4',
  'on-background': '#f4f4f4',
  'on-primary': '#161616',
  'on-secondary': '#161616',
}

export default createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        dark: false,
        colors: carbonColors,
        variables: {
          // Border radius following Carbon
          'border-radius-root': '4px',
          // Elevation/shadows
          'high-emphasis-opacity': 0.87,
          'medium-emphasis-opacity': 0.6,
          'disabled-opacity': 0.38,
        }
      },
      dark: {
        dark: true,
        colors: carbonDarkColors,
        variables: {
          'border-radius-root': '4px',
          'high-emphasis-opacity': 0.87,
          'medium-emphasis-opacity': 0.6,
          'disabled-opacity': 0.38,
        }
      }
    }
  },
  defaults: {
    // Global component defaults following Carbon patterns
    VCard: {
      elevation: 0,
      rounded: 'lg',
      border: true,
    },
    VBtn: {
      rounded: 'md',
      elevation: 0,
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VAutocomplete: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VCombobox: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VTextarea: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VCheckbox: {
      color: 'primary',
    },
    VRadio: {
      color: 'primary',
    },
    VSwitch: {
      color: 'primary',
      inset: true,
    },
    VChip: {
      rounded: 'lg',
    },
    VAlert: {
      rounded: 'md',
      border: 'start',
      variant: 'tonal',
    },
    VSnackbar: {
      rounded: 'md',
    },
    VDataTable: {
      hover: true,
    },
    VList: {
      rounded: 'md',
    },
    VListItem: {
      rounded: 'md',
    },
    VMenu: {
      rounded: 'md',
    },
    VDialog: {
      rounded: 'lg',
    },
    VProgressLinear: {
      rounded: true,
    },
    VProgressCircular: {
      width: 3,
    },
    VTabs: {
      color: 'primary',
    },
    VTab: {
      rounded: 'md',
    },
    VTooltip: {
      location: 'bottom',
    },
  }
})
