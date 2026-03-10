<template>
  <v-btn
    icon
    @click="themeStore.toggleTheme()"
    :aria-label="$t('navigation.toggleDarkMode')"
  >
    <v-icon aria-hidden="true">
      {{ themeStore.isDark ? 'mdi-weather-sunny' : 'mdi-weather-night' }}
    </v-icon>
  </v-btn>
</template>

<script setup>
import { useThemeStore } from '@/stores/themeStore'

const themeStore = useThemeStore()
</script>
