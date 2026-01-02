import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'

export default createVuetify({
  components,
  directives,
  theme: {
    themes: {
      light: {
        colors: {
          primary: '#1a237e',
          secondary: '#0d47a1',
          success: '#2e7d32',
          warning: '#f57c00',
          error: '#c62828',
        }
      }
    }
  }
})
