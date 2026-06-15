// main.css MUST be imported first: it declares the master cascade-layer
// order (@layer ...) that reconciles Vuetify 4's vuetify-* layers with
// Tailwind 4's preflight. The order is fixed by the first @layer statement
// the bundle parses, so this import has to precede vuetify/styles.
import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import vuetify from './plugins/vuetify'
import i18n from './i18n'

import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community'
ModuleRegistry.registerModules([AllCommunityModule])

import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-material.css'
import './assets/aggrid-theme.css'

import './assets/responsive.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(vuetify)
app.use(i18n)

app.mount('#app')
