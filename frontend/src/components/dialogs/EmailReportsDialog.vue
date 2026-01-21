<template>
  <v-dialog v-model="dialogVisible" max-width="600" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon start color="primary">mdi-email-outline</v-icon>
        Email Report Configuration
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" @click="close" />
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <v-alert
          v-if="successMessage"
          type="success"
          variant="tonal"
          closable
          class="mb-4"
          @click:close="successMessage = ''"
        >
          {{ successMessage }}
        </v-alert>

        <v-alert
          v-if="errorMessage"
          type="error"
          variant="tonal"
          closable
          class="mb-4"
          @click:close="errorMessage = ''"
        >
          {{ errorMessage }}
        </v-alert>

        <!-- Enable/Disable Toggle -->
        <v-switch
          v-model="config.enabled"
          label="Enable Automated Email Reports"
          color="primary"
          hide-details
          class="mb-4"
        />

        <v-expand-transition>
          <div v-if="config.enabled">
            <!-- Frequency Selection -->
            <v-select
              v-model="config.frequency"
              :items="frequencyOptions"
              item-title="text"
              item-value="value"
              label="Report Frequency"
              variant="outlined"
              density="comfortable"
              class="mb-4"
            />

            <!-- Report Time -->
            <v-text-field
              v-model="config.report_time"
              type="time"
              label="Report Delivery Time"
              variant="outlined"
              density="comfortable"
              hint="Time when reports will be sent"
              persistent-hint
              class="mb-4"
            />

            <!-- Email Recipients -->
            <v-label class="text-body-2 mb-2">Email Recipients</v-label>
            <v-combobox
              v-model="config.recipients"
              :items="suggestedEmails"
              label="Add email addresses"
              variant="outlined"
              density="comfortable"
              multiple
              chips
              closable-chips
              :rules="[validateEmails]"
              hint="Press Enter to add each email address"
              persistent-hint
              class="mb-4"
            >
              <template v-slot:chip="{ item, props }">
                <v-chip v-bind="props" closable>
                  <v-icon start size="small">mdi-email</v-icon>
                  {{ item.title }}
                </v-chip>
              </template>
            </v-combobox>

            <v-divider class="my-4" />

            <!-- Report Content Options -->
            <v-label class="text-body-2 mb-2">Report Content</v-label>
            <v-checkbox
              v-model="config.include_executive_summary"
              label="Executive Summary"
              hide-details
              density="compact"
            />
            <v-checkbox
              v-model="config.include_efficiency"
              label="Production Efficiency"
              hide-details
              density="compact"
            />
            <v-checkbox
              v-model="config.include_quality"
              label="Quality Metrics (FPY, PPM, DPMO)"
              hide-details
              density="compact"
            />
            <v-checkbox
              v-model="config.include_availability"
              label="Equipment Availability"
              hide-details
              density="compact"
            />
            <v-checkbox
              v-model="config.include_attendance"
              label="Attendance & Absenteeism"
              hide-details
              density="compact"
            />
            <v-checkbox
              v-model="config.include_predictions"
              label="Forecasts & Predictions"
              hide-details
              density="compact"
              class="mb-4"
            />
          </div>
        </v-expand-transition>

        <!-- Test Email Section -->
        <v-divider class="my-4" />

        <div class="d-flex align-center">
          <v-text-field
            v-model="testEmail"
            label="Test Email Address"
            variant="outlined"
            density="compact"
            hide-details
            class="mr-2"
            style="max-width: 300px"
          />
          <v-btn
            color="secondary"
            variant="outlined"
            :loading="sendingTest"
            :disabled="!testEmail || !isValidEmail(testEmail)"
            @click="sendTestEmail"
          >
            <v-icon start>mdi-send</v-icon>
            Send Test
          </v-btn>
        </div>
        <div class="text-caption text-grey-darken-1 mt-1">
          Send a test email to verify your configuration
        </div>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-4">
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-spacer />
        <v-btn
          color="primary"
          variant="flat"
          :loading="saving"
          @click="saveConfig"
        >
          <v-icon start>mdi-content-save</v-icon>
          Save Configuration
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import api from '@/services/api'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  clientId: {
    type: [String, Number],
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const config = ref({
  enabled: false,
  frequency: 'daily',
  report_time: '06:00',
  recipients: [],
  include_executive_summary: true,
  include_efficiency: true,
  include_quality: true,
  include_availability: true,
  include_attendance: true,
  include_predictions: true
})

const frequencyOptions = [
  { text: 'Daily', value: 'daily' },
  { text: 'Weekly (Monday)', value: 'weekly' },
  { text: 'Monthly (1st of month)', value: 'monthly' }
]

const suggestedEmails = ref([])
const testEmail = ref('')
const saving = ref(false)
const sendingTest = ref(false)
const successMessage = ref('')
const errorMessage = ref('')

// Load config when dialog opens
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    await loadConfig()
  }
})

const loadConfig = async () => {
  try {
    const response = await api.getEmailReportConfig(props.clientId)
    if (response.data) {
      config.value = {
        ...config.value,
        ...response.data
      }
    }
  } catch (error) {
    console.error('Failed to load email config:', error)
    // Use defaults if load fails
  }
}

const isValidEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

const validateEmails = (emails) => {
  if (!emails || emails.length === 0) return true
  const invalidEmails = emails.filter(e => !isValidEmail(e))
  if (invalidEmails.length > 0) {
    return `Invalid email(s): ${invalidEmails.join(', ')}`
  }
  return true
}

const saveConfig = async () => {
  saving.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    // Validate recipients if enabled
    if (config.value.enabled && config.value.recipients.length === 0) {
      errorMessage.value = 'Please add at least one email recipient'
      saving.value = false
      return
    }

    const payload = {
      ...config.value,
      client_id: props.clientId
    }

    await api.saveEmailReportConfig(payload)
    successMessage.value = 'Email report configuration saved successfully!'
    emit('saved', config.value)

    // Close after short delay
    setTimeout(() => {
      close()
    }, 1500)
  } catch (error) {
    console.error('Failed to save email config:', error)
    errorMessage.value = error.response?.data?.detail || 'Failed to save configuration. Please try again.'
  } finally {
    saving.value = false
  }
}

const sendTestEmail = async () => {
  sendingTest.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await api.sendTestEmail(testEmail.value)
    successMessage.value = `Test email sent to ${testEmail.value}`
  } catch (error) {
    console.error('Failed to send test email:', error)
    errorMessage.value = error.response?.data?.detail || 'Failed to send test email. Check your email configuration.'
  } finally {
    sendingTest.value = false
  }
}

const close = () => {
  dialogVisible.value = false
  successMessage.value = ''
  errorMessage.value = ''
}
</script>
