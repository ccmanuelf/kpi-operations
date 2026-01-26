<template>
  <v-btn-toggle
    v-model="currentLanguage"
    mandatory
    density="compact"
    color="primary"
    variant="outlined"
    class="language-toggle"
    :aria-label="$t('language.select')"
    role="group"
  >
    <v-btn
      value="en"
      size="small"
      :aria-label="$t('language.english')"
      :aria-pressed="currentLanguage === 'en'"
      class="language-btn"
    >
      <span class="d-none d-sm-inline">EN</span>
      <span class="d-inline d-sm-none">EN</span>
    </v-btn>
    <v-btn
      value="es"
      size="small"
      :aria-label="$t('language.spanish')"
      :aria-pressed="currentLanguage === 'es'"
      class="language-btn"
    >
      <span class="d-none d-sm-inline">ES</span>
      <span class="d-inline d-sm-none">ES</span>
    </v-btn>
  </v-btn-toggle>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { setLanguage, getLanguage } from '@/i18n'

const { locale } = useI18n()

// Computed property to sync with toggle
const currentLanguage = computed({
  get: () => locale.value,
  set: (newLocale) => {
    setLanguage(newLocale)
  }
})

// Initialize from localStorage on mount
const savedLanguage = getLanguage()
if (savedLanguage && savedLanguage !== locale.value) {
  setLanguage(savedLanguage)
}
</script>

<style scoped>
.language-toggle {
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
}

.language-btn {
  min-width: 36px !important;
  font-weight: 600;
  letter-spacing: 0.5px;
}

/* Make toggle buttons white text on primary app bar */
.v-app-bar .language-toggle {
  border-color: rgba(255, 255, 255, 0.5);
}

.v-app-bar .language-toggle .v-btn {
  color: white;
  border-color: rgba(255, 255, 255, 0.3);
}

.v-app-bar .language-toggle .v-btn--active {
  background-color: rgba(255, 255, 255, 0.2) !important;
}
</style>
