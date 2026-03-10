/**
 * Composable for theme-aware Chart.js defaults.
 * Returns reactive option fragments that respond to Vuetify's current theme.
 */
import { computed } from 'vue'
import { useTheme } from 'vuetify'

export function useChartTheme() {
  let theme
  try {
    theme = useTheme()
  } catch {
    theme = null
  }

  const isDark = computed(() => theme?.global?.current?.value?.dark ?? false)

  const scaleDefaults = computed(() => ({
    ticks: {
      color: isDark.value ? '#c6c6c6' : '#525252'
    },
    grid: {
      color: isDark.value ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'
    }
  }))

  const legendDefaults = computed(() => ({
    labels: {
      color: isDark.value ? '#f4f4f4' : '#161616'
    }
  }))

  // Theme-aware chart line/fill colors (WCAG 3:1 graphical contrast on dark bg)
  const chartColors = computed(() => isDark.value ? {
    green: '#42be65',
    greenFill: 'rgba(66, 190, 101, 0.18)',
    blue: '#4589ff',
    blueFill: 'rgba(69, 137, 255, 0.18)',
    darkBlue: '#4589ff',
    darkBlueFill: 'rgba(69, 137, 255, 0.18)',
    purple: '#be95ff',
    purpleFill: 'rgba(190, 149, 255, 0.18)',
    purpleBorder: 'rgba(190, 149, 255, 0.3)',
    purpleConfidence: 'rgba(190, 149, 255, 0.1)',
    red: '#ff8389',
    redFill: 'rgba(255, 131, 137, 0.18)',
    orange: '#f57c00'
  } : {
    green: '#2e7d32',
    greenFill: 'rgba(46, 125, 50, 0.18)',
    blue: '#1976d2',
    blueFill: 'rgba(25, 118, 210, 0.18)',
    darkBlue: '#0d47a1',
    darkBlueFill: 'rgba(13, 71, 161, 0.18)',
    purple: '#7b1fa2',
    purpleFill: 'rgba(123, 31, 162, 0.18)',
    purpleBorder: 'rgba(156, 39, 176, 0.3)',
    purpleConfidence: 'rgba(156, 39, 176, 0.1)',
    red: '#d32f2f',
    redFill: 'rgba(211, 47, 47, 0.18)',
    orange: '#f57c00'
  })

  return {
    isDark,
    scaleDefaults,
    legendDefaults,
    chartColors
  }
}
