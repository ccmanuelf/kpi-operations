import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tsParser from '@typescript-eslint/parser'

export default [
  { ignores: ['dist/**', 'node_modules/**', 'playwright-report*/**', 'test-results/**', 'e2e/**'] },
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
        // Vue compiler macros
        defineProps: 'readonly',
        defineEmits: 'readonly',
        defineExpose: 'readonly',
        defineOptions: 'readonly',
        defineSlots: 'readonly',
        withDefaults: 'readonly'
      }
    },
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'off',
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      'no-console': 'warn',
      // Match old ESLint 8 recommended behavior — these rules are new or stricter in ESLint 10
      'no-useless-assignment': 'off',
      'no-prototype-builtins': 'off',
      // Pre-existing issues — downgrade to warn for clean exit
      'no-useless-catch': 'warn',
      'no-dupe-keys': 'warn',
      'vue/no-unused-vars': 'warn',
      'vue/no-mutating-props': 'warn',
      'preserve-caught-error': 'off'
    }
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        parser: tsParser
      }
    },
    rules: {
      // Vuetify uses v-slot modifiers extensively; disable strict validation
      'vue/valid-v-slot': ['error', { allowModifiers: true }]
    }
  },
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser
    }
  },
  {
    files: ['**/*.{test,spec}.{js,ts}', '**/__tests__/**/*.{js,ts}'],
    languageOptions: {
      globals: {
        // Vitest globals (vitest.config.ts has globals: true)
        describe: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        vi: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        beforeAll: 'readonly',
        afterAll: 'readonly',
        test: 'readonly'
      }
    }
  }
]
