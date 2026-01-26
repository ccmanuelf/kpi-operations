import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * Vite Configuration - Performance Optimized
 *
 * Key optimizations:
 * 1. Manual chunk splitting for better caching
 * 2. Vendor chunks separated by update frequency
 * 3. Lazy-loaded routes in separate chunks
 * 4. Compression for production builds
 */
export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },

  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },

  build: {
    // Target modern browsers for smaller bundles
    target: 'es2020',

    // Enable source maps for production debugging (optional)
    sourcemap: false,

    // Increase chunk size warning limit (after optimization)
    chunkSizeWarningLimit: 600,

    // Minification options
    minify: 'esbuild',
    cssMinify: true,

    // Rollup options for chunk splitting
    rollupOptions: {
      output: {
        /**
         * Manual chunk splitting strategy:
         *
         * 1. vendor-core: Vue, Vue Router, Pinia (rarely changes)
         * 2. vendor-ui: Vuetify (changes with UI updates)
         * 3. vendor-charts: Chart.js (only needed for dashboards)
         * 4. vendor-grid: AG Grid (only needed for data entry)
         * 5. vendor-utils: date-fns, papaparse (utility libraries)
         * 6. vendor-qr: QR code libraries (rarely used)
         * 7. Default chunks for app code
         */
        manualChunks(id) {
          // Skip non-node_modules
          if (!id.includes('node_modules')) {
            return undefined
          }

          // Core Vue ecosystem - rarely changes, cached long-term
          if (
            id.includes('vue') ||
            id.includes('pinia') ||
            id.includes('vue-router')
          ) {
            // Exclude vue-chartjs and vue-qrcode from core
            if (id.includes('vue-chartjs') || id.includes('vue-qrcode') || id.includes('qrcode.vue')) {
              return undefined // Handle separately
            }
            return 'vendor-core'
          }

          // Vuetify UI framework - separate for independent updates
          if (id.includes('vuetify') || id.includes('@mdi/font')) {
            return 'vendor-ui'
          }

          // Chart.js ecosystem - lazy loaded with dashboards
          if (id.includes('chart.js') || id.includes('vue-chartjs')) {
            return 'vendor-charts'
          }

          // AG Grid - lazy loaded with data entry views
          if (id.includes('ag-grid')) {
            return 'vendor-grid'
          }

          // CSV parsing - only needed for imports
          if (id.includes('papaparse')) {
            return 'vendor-csv'
          }

          // Date utilities - frequently used
          if (id.includes('date-fns')) {
            return 'vendor-date'
          }

          // QR code libraries - rarely used
          if (id.includes('qrcode') || id.includes('vue-qrcode-reader')) {
            return 'vendor-qr'
          }

          // Drag and drop - for dashboard customization
          if (id.includes('vuedraggable') || id.includes('sortablejs')) {
            return 'vendor-dnd'
          }

          // Axios - HTTP client
          if (id.includes('axios')) {
            return 'vendor-http'
          }

          // All other node_modules
          return 'vendor-misc'
        },

        // Consistent chunk naming for long-term caching
        chunkFileNames: (chunkInfo) => {
          // Use content hash for cache busting
          return `assets/${chunkInfo.name}-[hash].js`
        },

        // Asset file naming
        assetFileNames: (assetInfo) => {
          // Keep fonts in a dedicated folder
          if (assetInfo.name && /\.(woff2?|eot|ttf|otf)$/.test(assetInfo.name)) {
            return 'assets/fonts/[name]-[hash][extname]'
          }
          // Keep images organized
          if (assetInfo.name && /\.(png|jpe?g|gif|svg|webp|ico)$/.test(assetInfo.name)) {
            return 'assets/images/[name]-[hash][extname]'
          }
          return 'assets/[name]-[hash][extname]'
        },

        // Entry point naming
        entryFileNames: 'assets/[name]-[hash].js'
      }
    }
  },

  // Optimize dependency pre-bundling
  optimizeDeps: {
    include: [
      'vue',
      'vue-router',
      'pinia',
      'axios',
      'date-fns'
    ],
    // Exclude heavy libraries from pre-bundling (they'll be lazy loaded)
    exclude: [
      'papaparse',
      'vue-qrcode-reader'
    ]
  },

  // CSS optimization
  css: {
    devSourcemap: true,
    preprocessorOptions: {
      // Add any SCSS/SASS options here if needed
    }
  },

  // Preview server configuration (for testing production builds)
  preview: {
    port: 4173,
    strictPort: true
  }
})
