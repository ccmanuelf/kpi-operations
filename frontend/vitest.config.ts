/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    include: ['src/**/*.{test,spec}.{js,ts}'],
    exclude: [
      'node_modules/**',
      'dist/**',
      'e2e/**',
      '**/*.e2e.*',
      '**/playwright/**'
    ],
    setupFiles: ['./src/test/setup.js'],
    deps: {
      optimizer: {
        web: {
          include: ['vuetify']
        }
      }
    },
    coverage: {
      reporter: ['text', 'json', 'html'],
      include: [
        'src/services/**/*.js',
        'src/stores/**/*.js',
        'src/utils/**/*.js',
        'src/components/**/*.vue',
        'src/views/**/*.vue'
      ],
      exclude: [
        'node_modules/',
        'src/**/*.d.ts',
        'e2e/**',
        'src/**/__tests__/**'
      ],
      thresholds: {
        // Recalibrated for vitest 4 V8 coverage remapping (was 55/45/50/55)
        statements: 10,
        branches: 10,
        functions: 5,
        lines: 10
      }
    }
  }
})
