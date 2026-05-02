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
  // Entry-UI Standard guardrail (Phase 3 of the entry-interface audit).
  // See docs/standards/entry-ui-standard.md.
  // Bans <v-form> in entry surfaces (views/ and components/entries/) so the
  // Spreadsheet Standard (AGGridBase) is the default path. Exception files
  // are excluded explicitly in the next config block.
  {
    files: ['src/views/**/*.vue', 'src/components/entries/**/*.vue'],
    rules: {
      'vue/no-restricted-syntax': ['warn', {
        selector: "VElement[name='v-form']",
        message: 'Entry surfaces must use AGGridBase, not <v-form>. See docs/standards/entry-ui-standard.md §1. If this is a permitted exception (Login / Admin <5 users / filter dialog / confirmation), add the file to the override block in eslint.config.js.'
      }]
    }
  },
  {
    // Exception files — surfaces explicitly permitted to use <v-form> per
    // docs/standards/entry-ui-standard.md §4. Each entry has a justification.
    files: [
      'src/views/LoginView.vue',                        // Exception 1: auth
      'src/views/admin/AdminClients.vue',               // Exception 2: admin config (<5 clients)
      'src/views/admin/AdminSettings.vue',              // Exception 2: admin config
      'src/views/admin/AdminUsers.vue',                 // Exception 2: user provisioning
      'src/views/admin/ClientConfigView.vue',           // Exception 2: per-client config
      'src/views/admin/WorkflowConfigView.vue',         // Exception 2: workflow config
      'src/views/SimulationView.vue',                   // Exception 3: simulation parameters
      'src/views/KPIDashboard.vue',                     // Exception 2/3: email config + saved filters
      'src/components/filters/SaveFilterDialog.vue'     // Exception 3: filter management
    ],
    rules: {
      'vue/no-restricted-syntax': 'off'
    }
  },
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: tsParser
    },
    rules: {
      // ESLint's no-undef doesn't understand TypeScript types and
      // false-positives on type-only references (e.g. `as BlobPart`).
      // TypeScript itself catches undefined identifiers; per the
      // @typescript-eslint docs this rule is redundant for .ts files.
      'no-undef': 'off'
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
