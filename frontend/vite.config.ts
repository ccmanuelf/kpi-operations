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
        // Split vendor chunks for better caching in production
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          vuetify: ['vuetify'],
          charts: ['chart.js', 'vue-chartjs'],
          aggrid: ['ag-grid-community', 'ag-grid-vue3']
        }
      }
    }
  }
})
