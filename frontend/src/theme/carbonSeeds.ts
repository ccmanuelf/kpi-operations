// IBM Carbon brand hues — the SEEDS for the MD3 tonal system (Vuetify 4 + MD3).
// These are the single source of brand color. md3Tonal.ts derives MD3 role
// tokens (primary/on-primary/containers/surfaces, light+dark) from them.
// Values copied verbatim from the light theme in src/plugins/vuetify.ts.
export const carbonSeeds = {
  primary: '#0f62fe',
  secondary: '#393939',
  success: '#198038',
  error: '#da1e28',
  info: '#0072c3',
  warning: '#f1c21b',
} as const

export type CarbonSeedKey = keyof typeof carbonSeeds
