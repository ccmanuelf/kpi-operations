/**
 * Vitest Configuration for Frontend Tests
 * Vue.js 3 component and integration testing
 */

import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import path from 'path';

export default defineConfig({
  plugins: [vue()],

  test: {
    // Test environment
    environment: 'jsdom',

    // Global test settings
    globals: true,

    // Setup files
    setupFiles: ['./tests/setup.js'],

    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      reportsDirectory: './tests/coverage',

      // Coverage thresholds (90% minimum)
      lines: 90,
      functions: 90,
      branches: 90,
      statements: 90,

      // Files to include/exclude
      include: ['src/**/*.{js,vue}'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.spec.js',
        '**/*.test.js',
        'src/main.js'
      ]
    },

    // Test patterns
    include: ['tests/**/*.{test,spec}.{js,ts}'],

    // Test timeout
    testTimeout: 10000,

    // Reporter
    reporters: ['verbose', 'html'],

    // Mock settings
    mockReset: true,
    restoreMocks: true
  },

  // Resolve aliases (match vite.config)
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '../src'),
      '@components': path.resolve(__dirname, '../src/components'),
      '@views': path.resolve(__dirname, '../src/views'),
      '@stores': path.resolve(__dirname, '../src/stores'),
      '@utils': path.resolve(__dirname, '../src/utils')
    }
  }
});
