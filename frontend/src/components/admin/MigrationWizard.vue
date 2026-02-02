<template>
  <v-card variant="outlined">
    <v-stepper v-model="step" :items="stepItems" alt-labels>
      <!-- Step 1: Select Target Provider -->
      <template v-slot:item.1>
        <v-card flat class="pa-4">
          <h3 class="text-h6 mb-4">Select Target Database</h3>

          <v-radio-group v-model="targetProvider" class="mb-4">
            <v-radio value="mariadb">
              <template v-slot:label>
                <div>
                  <strong>MariaDB</strong>
                  <span class="text-success ml-2">(Recommended)</span>
                  <p class="text-body-2 text-medium-emphasis mb-0">
                    Open-source, MySQL-compatible database with excellent performance
                  </p>
                </div>
              </template>
            </v-radio>

            <v-radio value="mysql" class="mt-3">
              <template v-slot:label>
                <div>
                  <strong>MySQL</strong>
                  <p class="text-body-2 text-medium-emphasis mb-0">
                    Widely-used relational database
                  </p>
                </div>
              </template>
            </v-radio>
          </v-radio-group>

          <v-text-field
            v-model="targetUrl"
            label="Database Connection URL"
            :placeholder="urlPlaceholder"
            :hint="urlHint"
            persistent-hint
            variant="outlined"
            class="mb-4"
          />

          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            <v-alert-title>Connection URL Format</v-alert-title>
            <code>mysql+pymysql://username:password@hostname:port/database_name</code>
          </v-alert>
        </v-card>
      </template>

      <!-- Step 2: Test Connection -->
      <template v-slot:item.2>
        <v-card flat class="pa-4">
          <h3 class="text-h6 mb-4">Test Connection</h3>

          <p class="text-body-2 mb-4">
            Click the button below to verify the connection to your target database.
          </p>

          <div class="d-flex align-center mb-4">
            <v-btn
              color="primary"
              @click="testConnection"
              :loading="isLoading"
              :disabled="!targetUrl"
            >
              <v-icon start>mdi-connection</v-icon>
              Test Connection
            </v-btn>
          </div>

          <!-- Connection Result -->
          <v-alert
            v-if="connectionTestResult"
            :type="connectionTestResult.success ? 'success' : 'error'"
            variant="tonal"
            class="mt-4"
          >
            <v-alert-title>
              {{ connectionTestResult.success ? 'Connection Successful' : 'Connection Failed' }}
            </v-alert-title>
            <p class="mb-0">{{ connectionTestResult.message }}</p>
            <template v-if="connectionTestResult.success && connectionTestResult.connection_info">
              <v-divider class="my-2" />
              <div class="text-body-2">
                <strong>Provider:</strong> {{ connectionTestResult.provider }}<br>
                <strong>Host:</strong> {{ connectionTestResult.connection_info.host }}<br>
                <strong>Database:</strong> {{ connectionTestResult.connection_info.database }}
              </div>
            </template>
          </v-alert>
        </v-card>
      </template>

      <!-- Step 3: Confirm Migration -->
      <template v-slot:item.3>
        <v-card flat class="pa-4">
          <h3 class="text-h6 mb-4">Confirm Migration</h3>

          <v-alert type="error" variant="outlined" class="mb-4">
            <v-alert-title>Final Warning</v-alert-title>
            <p>
              This action is <strong>irreversible</strong>. You are about to:
            </p>
            <ul class="mb-2">
              <li>Create schema on <strong>{{ targetProvider.toUpperCase() }}</strong></li>
              <li>Seed demo data on the new database</li>
              <li>Switch the application to use the new database</li>
            </ul>
            <p class="mb-0">
              Type <code>MIGRATE</code> below to confirm this operation.
            </p>
          </v-alert>

          <v-text-field
            v-model="confirmationText"
            label="Type MIGRATE to confirm"
            variant="outlined"
            :rules="[v => v === 'MIGRATE' || 'You must type MIGRATE exactly']"
            class="mb-4"
          />

          <v-btn
            color="error"
            size="large"
            :disabled="confirmationText !== 'MIGRATE' || isLoading"
            :loading="isLoading"
            @click="startMigration"
          >
            <v-icon start>mdi-database-arrow-right</v-icon>
            Start Migration
          </v-btn>
        </v-card>
      </template>

      <!-- Stepper Actions -->
      <template v-slot:actions>
        <v-stepper-actions
          @click:prev="step--"
          @click:next="handleNext"
          :disabled="nextDisabled"
        />
      </template>
    </v-stepper>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'

// Props
const props = defineProps({
  connectionTestResult: {
    type: Object,
    default: null
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['start', 'test-connection'])

// State
const step = ref(1)
const targetProvider = ref('mariadb')
const targetUrl = ref('')
const confirmationText = ref('')

// Stepper items
const stepItems = ['Select Target', 'Test Connection', 'Confirm']

// Computed
const urlPlaceholder = computed(() => {
  if (targetProvider.value === 'mariadb') {
    return 'mysql+pymysql://user:password@localhost:3306/kpi_platform'
  }
  return 'mysql+mysqlconnector://user:password@localhost:3306/kpi_platform'
})

const urlHint = computed(() => {
  if (targetProvider.value === 'mariadb') {
    return 'MariaDB uses the PyMySQL driver (mysql+pymysql://)'
  }
  return 'MySQL can use MySQL Connector (mysql+mysqlconnector://)'
})

const nextDisabled = computed(() => {
  if (step.value === 1) {
    return !targetUrl.value || !targetProvider.value
  }
  if (step.value === 2) {
    return !props.connectionTestResult?.success
  }
  return false
})

// Methods
function handleNext() {
  if (step.value < 3) {
    step.value++
  }
}

async function testConnection() {
  emit('test-connection', targetUrl.value)
}

function startMigration() {
  emit('start', {
    targetProvider: targetProvider.value,
    targetUrl: targetUrl.value,
    confirmationText: confirmationText.value
  })
}
</script>
