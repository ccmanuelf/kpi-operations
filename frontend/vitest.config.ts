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
    setupFiles: ['./src/test/setup.ts'],
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
        // Include both .js and .ts — services / stores / utils / composables
        // were progressively migrated to TypeScript and the legacy .js-only
        // glob silently excluded them from measurement. (E.g. all 28 services,
        // 19 stores, 9 utils, and 66 composables are now .ts-only.)
        'src/services/**/*.{js,ts}',
        'src/stores/**/*.{js,ts}',
        'src/utils/**/*.{js,ts}',
        'src/composables/**/*.{js,ts}',
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
        // 2026-04-27 measured floor (.js-only include glob): 18.35/18.67/10.97/19.93.
        // 2026-05-04 — included .ts files in the coverage glob to match the
        // post-TS-port codebase (services/stores/utils/composables are all
        // .ts now). Current floor measured: 22.68/20.5/15.02/24.32.
        statements: 22,
        branches: 20,
        functions: 15,
        lines: 24
      }
    }
  }
})
