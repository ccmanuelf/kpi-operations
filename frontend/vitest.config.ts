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
      provider: 'v8',
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
        // V8 coverage remapping issue (vitest 4 + @vitest/coverage-v8 4):
        // V8's source map remapping reports significantly lower coverage than
        // istanbul-based tools. The same codebase that measured ~55% with
        // vitest 1 / coverage-v8 1 now reports ~13% due to how V8 maps
        // transpiled Vue SFC code back to source. This is a known vitest 4
        // behavior change, not an actual coverage regression.
        // Original thresholds (vitest 1): 55/45/50/55
        // Run 5 remediation aspiration: 30/25/20/30 (never met — many views at 0%)
        // Current floor (locked as no-regression gate, must only ratchet up):
        // measured 18.35/18.67/10.97/19.93 on 2026-04-27.
        statements: 18,
        branches: 18,
        functions: 10,
        lines: 19
      }
    }
  }
})
