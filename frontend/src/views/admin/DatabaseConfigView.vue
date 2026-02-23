<template>
  <v-container fluid class="pa-6">
    <v-row>
      <v-col cols="12">
        <!-- Page Header -->
        <div class="d-flex align-center mb-6">
          <v-icon size="32" color="primary" class="mr-3">mdi-database-cog</v-icon>
          <div>
            <h1 class="text-h4">{{ t('databaseConfig.title') }}</h1>
            <p class="text-body-2 text-medium-emphasis mb-0">
              {{ t('databaseConfig.subtitle') }}
            </p>
          </div>
        </div>

        <!-- Current Status Card -->
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

            <!-- Connection Info -->
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
          </v-card-text>
        </v-card>

        <!-- Migration Section (SQLite only) -->
        <v-card v-if="canMigrate">
          <v-card-title class="d-flex align-center">
            <v-icon start>mdi-database-arrow-right</v-icon>
            {{ t('databaseConfig.migrateTitle') }}
            <v-chip class="ml-2" color="warning" size="small">{{ t('common.optional') }}</v-chip>
          </v-card-title>

          <v-card-text>
            <!-- Warning Alert -->
            <v-alert type="warning" variant="outlined" class="mb-4">
              <v-alert-title>{{ t('databaseConfig.oneWayMigration') }}</v-alert-title>
              <p class="mb-0">
                {{ t('databaseConfig.oneWayWarning') }}
              </p>
              <ul class="mt-2 mb-0">
                <li>{{ t('databaseConfig.createTables') }}</li>
                <li>{{ t('databaseConfig.seedDemoData') }}</li>
                <li>{{ t('databaseConfig.updateApp') }}</li>
              </ul>
            </v-alert>

            <!-- Migration Wizard or Progress -->
            <MigrationWizard
              v-if="!isMigrating && !migrationCompleted && !migrationFailed"
              @start="handleMigrationStart"
              @test-connection="handleTestConnection"
              :connection-test-result="connectionTestResult"
              :is-loading="isLoading"
            />

            <MigrationProgress
              v-else
              :status="migrationStatus"
              :progress="migrationProgress"
              @dismiss="handleDismissProgress"
            />
          </v-card-text>
        </v-card>

        <!-- Already Migrated -->
        <v-card v-else>
          <v-card-title class="d-flex align-center">
            <v-icon start color="success">mdi-check-circle</v-icon>
            {{ t('databaseConfig.productionDbActive') }}
          </v-card-title>

          <v-card-text>
            <v-alert type="success" variant="tonal">
              <p class="mb-0">
                {{ t('databaseConfig.noFurtherMigration', { provider: providerDisplayName }) }}
              </p>
            </v-alert>
          </v-card-text>
        </v-card>

        <!-- Error Display -->
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useDatabaseConfigStore } from '@/stores/databaseConfigStore'
import MigrationWizard from '@/components/admin/MigrationWizard.vue'
import MigrationProgress from '@/components/admin/MigrationProgress.vue'

const { t } = useI18n()

// Store
const store = useDatabaseConfigStore()
const {
  currentProvider,
  connectionInfo,
  canMigrate,
  isMigrating,
  migrationStatus,
  migrationProgress,
  migrationCompleted,
  migrationFailed,
  providerDisplayName,
  isLoading,
  error,
  connectionTestResult
} = storeToRefs(store)

// Local state
const showError = ref(false)

// Computed
const providerIcon = computed(() => {
  const icons = {
    sqlite: 'mdi-database',
    mariadb: 'mdi-database-check',
    mysql: 'mdi-database-check',
    postgresql: 'mdi-database-check'
  }
  return icons[currentProvider.value] || 'mdi-database'
})

// Watch for errors
watch(error, (newError) => {
  if (newError) {
    showError.value = true
  }
})

// Lifecycle
onMounted(() => {
  store.fetchStatus()
  store.fetchProviders()
})

onUnmounted(() => {
  store.stopPolling()
})

// Methods
async function handleMigrationStart(config) {
  try {
    await store.startMigration(
      config.targetProvider,
      config.targetUrl,
      config.confirmationText
    )
  } catch (e) {
    // Error is handled by store
  }
}

async function handleTestConnection(url) {
  return await store.testConnection(url)
}

function handleDismissProgress() {
  store.clearMigrationStatus()
  store.fetchStatus()
}

function clearError() {
  showError.value = false
  store.clearError()
}
</script>
