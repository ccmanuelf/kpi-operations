/**
 * Ambient declarations.
 *
 * The JS→TS migration retired every per-module `any`-shim that
 * previously lived here. The only surviving declaration is the
 * `*.vue` catch-all for plain (non-`<script setup>`) Options-API
 * SFCs that the Volar plugin can't auto-type.
 */

// Vue SFCs without a colocated .d.ts — the Volar plugin handles
// `<script setup>`-defined components, but plain `<script>` SFCs that
// use the Options API need this catch-all.
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, any>
  export default component
}

// vue-router meta-field augmentation. Re-exported below so the standard
// ESLint `no-unused-vars` rule (used in lieu of
// `@typescript-eslint/no-unused-vars`) does not flag the merged
// interface name — declaration merging is a type-system construct
// invisible to ESLint's variable-tracker, and the re-export gives it a
// "use" it can see.
declare module 'vue-router' {
  export interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
  }
}
