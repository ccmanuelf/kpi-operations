import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vuetify from 'vite-plugin-vuetify'
import { fileURLToPath, URL } from 'node:url'

// Vite configuration for KPI Operations Frontend
// Docs: https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Auto-import Vuetify components and directives
    vuetify({ autoImport: true })
  ],
  resolve: {
    alias: {
      // Allow imports like '@/components/...' instead of relative paths
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    fs: {
      // Allow Vite to read project-root files like ../docs/user-guide/*.md
      // for the in-app Help Center (`?raw` imports).
      allow: ['..']
    },
    proxy: {
      // Proxy API requests to the FastAPI backend during development
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Vite 8 replaced Rollup with Rolldown, and the two disagree here.
        // The old `manualChunks` OBJECT form is Rollup-only; Rolldown fails
        // the build outright with `TypeError: manualChunks is not a function`.
        //
        // Converting it to a manualChunks FUNCTION builds, but is NOT
        // equivalent and quietly moves code: the object form seeded a chunk
        // with the listed modules AND their dependency closure, while a
        // path-matching function only claims files whose own path matches.
        // Measured on that version, Vue's reactivity runtime (@vue/*) landed
        // in the AG Grid chunk, and `vendor` shrank 152 kB -> 111 kB.
        //
        // `advancedChunks` is Rolldown's own replacement and takes the closure
        // with it. `@vue` and `@kurkle` are named explicitly because they are
        // exactly the transitive packages the object form used to absorb.
        //
        // Each pattern ends at a path separator: unanchored, `vue` also
        // matches vue-router, vue-chartjs and vuetify, collapsing four groups
        // into one.
        advancedChunks: {
          groups: [
            { name: 'vendor', test: /[\\/]node_modules[\\/](vue|vue-router|pinia|@vue)[\\/]/ },
            { name: 'vuetify', test: /[\\/]node_modules[\\/]vuetify[\\/]/ },
            { name: 'charts', test: /[\\/]node_modules[\\/](chart\.js|vue-chartjs|@kurkle)[\\/]/ },
            { name: 'aggrid', test: /[\\/]node_modules[\\/](ag-grid-community|ag-grid-vue3)[\\/]/ },
          ],
        },
      },
    }
  }
})
