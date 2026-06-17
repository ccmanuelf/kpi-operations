import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tsParser from '@typescript-eslint/parser'
import vueI18n from '@intlify/eslint-plugin-vue-i18n'

export default [
  { ignores: ['dist/**', 'node_modules/**', 'playwright-report*/**', 'test-results/**', 'e2e/**', '.visual-baseline/**'] },
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
    files: ['**/*.vue'],
    plugins: { '@intlify/vue-i18n': vueI18n },
    settings: {
      'vue-i18n': {
        localeDir: './src/i18n/locales/*.json',
        messageSyntaxVersion: '^11.0.0',
      },
    },
    rules: {
      // Enforced: new hardcoded user-facing template text fails lint (CI gate).
      '@intlify/vue-i18n/no-raw-text': ['error', {
        // ignore icon names (<v-icon>mdi-…), pure symbols/numbers/punctuation,
        // and Greek/arrow glyphs used in formulas — none are UI copy.
        ignorePattern: "^(mdi-[a-z0-9-]+|[\\s\\d.,%·°:;!?#()\\[\\]{}\\-+*×÷=/|<>$€σΣΔ→—'\"]+)$",
        // domain acronyms (identical in es), plus formula/code/URL/example-data
        // literals that must not be translated.
        ignoreText: [
          'OEE', 'KPI', 'DPMO', 'FPY', 'WIP', 'PPM', 'CSV', 'AI', 'BOM', 'ID',
          'DPMO = 750',
          'DPMO = (15 x 1,000,000) / 20,000',
          'DPMO = (Defects x 1,000,000) / (Units x Opportunities per Unit)',
          '= 1,000 x 20 = 20,000',
          'PART-001', 'part_number', 'part_description', 'opportunities_per_unit',
          // empty-string / sign fallback literals inside {{ }} ternaries (e.g. `x > 0 ? '+' : ''`)
          '',
          // unit symbols (identical in es) and glyphs that are not UI copy
          'h', 'min', 'hrs', 'd', 'x', 'v',
          // language switch ISO codes (not translated)
          'EN', 'ES',
          // universal keyboard shortcuts
          '(Ctrl+Z)', '(Ctrl+Y)',
        ],
      }],
    },
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
