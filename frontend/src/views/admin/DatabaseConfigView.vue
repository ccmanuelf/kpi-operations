<template>
  <v-container fluid class="pa-6">
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center mb-6">
          <v-icon size="32" color="primary" class="mr-3">mdi-database-cog</v-icon>
          <div>
            <h1 class="text-h4">{{ t('databaseConfig.title') }}</h1>
            <p class="text-body-2 text-medium-emphasis mb-0">
              {{ t('databaseConfig.subtitle') }}
            </p>
          </div>
        </div>

        <v-card class="mb-6">
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-database</v-icon>
            {{ t('databaseConfig.currentProvider') }}
          </v-card-title>

          <v-card-text>
            <v-alert
              :type="currentProvider === 'sqlite' ? 'info' : 'success'"
              variant="tonal"
              class="mb-4"
            >
              <div class="d-flex align-center">
                <v-icon :icon="providerIcon" class="mr-2" />
                <div>
                  <strong>{{ providerDisplayName }}</strong>
                  <template v-if="currentProvider === 'sqlite'">
                    <br>
                    <span class="text-body-2">
                      {{ t('databaseConfig.sqliteInfo') }}
                    </span>
                  </template>
                  <template v-else>
                    <br>
                    <span class="text-body-2">
                      {{ t('databaseConfig.productionActive') }}
                    </span>
                  </template>
                </div>
              </div>
            </v-alert>

            <v-table v-if="Object.keys(connectionInfo).length > 0" density="compact" class="mb-4">
              <thead>
                <tr>
                  <th>{{ t('databaseConfig.property') }}</th>
                  <th>{{ t('databaseConfig.value') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(value, key) in connectionInfo" :key="key">
                  <td class="text-capitalize">{{ key.replace(/_/g, ' ') }}</td>
                  <td><code>{{ value || t('common.na') }}</code></td>
                </tr>
              </tbody>
            </v-table>

            <v-alert type="info" variant="outlined" density="compact">
              {{ t('databaseConfig.schemaManagedByMigrations') }}
            </v-alert>
          </v-card-text>
        </v-card>

        <v-snackbar v-model="showError" color="error" :timeout="5000">
          {{ error }}
          <template v-slot:actions>
            <v-btn variant="text" @click="clearError">{{ t('common.close') }}</v-btn>
          </template>
        </v-snackbar>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useDatabaseConfigStore } from '@/stores/databaseConfigStore'

const { t } = useI18n()

const store = useDatabaseConfigStore()
const { currentProvider, connectionInfo, providerDisplayName, error } = storeToRefs(store)

const showError = ref(false)

const providerIcon = computed(() => {
  const icons = {
    sqlite: 'mdi-database',
    mariadb: 'mdi-database-check',
    mysql: 'mdi-database-check',
    postgresql: 'mdi-database-check'
  }
  return icons[currentProvider.value] || 'mdi-database'
})

watch(error, (newError) => {
  if (newError) {
    showError.value = true
  }
})

onMounted(() => {
  store.fetchStatus()
  store.fetchProviders()
})

function clearError() {
  showError.value = false
  store.clearError()
}
</script>
