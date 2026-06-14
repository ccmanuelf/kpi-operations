// Carbon-seeded Material Design 3 tonal token derivation.
//
// Each Carbon brand hue (see carbonSeeds.ts) is treated as an MD3 tonal-palette
// seed. We extract its HCT hue + chroma and read MD3 standard tones off the
// resulting tonal palette to produce the full set of Vuetify role tokens
// (base / on / container / on-container) plus the neutral surface roles.
//
// This module is pure and side-effect free; it does not touch the Vuetify
// plugin. Wiring into the theme happens in a later task.
import {
  argbFromHex,
  hexFromArgb,
  Hct,
  TonalPalette,
} from '@material/material-color-utilities'
import { carbonSeeds } from './carbonSeeds'

type Tone = number

const tone = (seedHex: string, t: Tone): string => {
  const hct = Hct.fromInt(argbFromHex(seedHex))
  const tp = TonalPalette.fromHueAndChroma(hct.hue, hct.chroma)
  return hexFromArgb(tp.tone(t))
}

// MD3 standard tones: light vs dark roles use mirrored tones.
const ROLE_TONES = {
  light: { base: 40, on: 100, container: 90, onContainer: 10, surface: 98, onSurface: 10 },
  dark: { base: 80, on: 20, container: 30, onContainer: 90, surface: 6, onSurface: 90 },
} as const

export interface VuetifyThemeColors {
  [k: string]: string
}

export interface VuetifyTheme {
  dark: boolean
  colors: VuetifyThemeColors
}

export function buildMd3Theme(mode: 'light' | 'dark'): VuetifyTheme {
  const T = ROLE_TONES[mode]
  const colors: VuetifyThemeColors = {
    background: tone(carbonSeeds.secondary, T.surface),
    surface: tone(carbonSeeds.secondary, T.surface),
    'on-surface': tone(carbonSeeds.secondary, T.onSurface),
    'on-background': tone(carbonSeeds.secondary, T.onSurface),
  }
  for (const key of Object.keys(carbonSeeds) as (keyof typeof carbonSeeds)[]) {
    colors[key] = tone(carbonSeeds[key], T.base)
    colors[`on-${key}`] = tone(carbonSeeds[key], T.on)
    colors[`${key}-container`] = tone(carbonSeeds[key], T.container)
    colors[`on-${key}-container`] = tone(carbonSeeds[key], T.onContainer)
  }
  return { dark: mode === 'dark', colors }
}

// WCAG relative-luminance contrast ratio between two #rrggbb colors.
export function contrastRatio(fg: string, bg: string): number {
  const lum = (hex: string): number => {
    const c = [1, 3, 5]
      .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
  }
  const a = lum(fg)
  const b = lum(bg)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}
