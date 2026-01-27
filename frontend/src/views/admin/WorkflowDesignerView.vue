<template>
  <v-container fluid class="pa-0 workflow-designer-view">
    <!-- Client selector header -->
    <v-card v-if="!selectedClient" class="ma-4">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-sitemap</v-icon>
        {{ $t('workflowDesigner.selectClient.title') }}
      </v-card-title>
      <v-card-subtitle>
        {{ $t('workflowDesigner.selectClient.subtitle') }}
      </v-card-subtitle>
      <v-card-text>
        <v-autocomplete
          v-model="selectedClientId"
          :items="clients"
          :loading="loadingClients"
          item-title="client_name"
          item-value="client_id"
          :label="$t('workflowDesigner.selectClient.label')"
          prepend-inner-icon="mdi-domain"
          variant="outlined"
          clearable
          @update:model-value="handleClientSelect"
        >
          <template v-slot:item="{ props, item }">
            <v-list-item v-bind="props">
              <template v-slot:prepend>
                <v-icon color="primary">mdi-domain</v-icon>
              </template>
              <v-list-item-subtitle>
                {{ $t('workflowDesigner.selectClient.clientId') }}: {{ item.raw.client_id }}
              </v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-autocomplete>
      </v-card-text>
    </v-card>

    <!-- Workflow Designer -->
    <div v-else class="designer-wrapper">
      <!-- Back button -->
      <v-btn
        variant="text"
        size="small"
        class="ma-2"
        @click="clearClient"
      >
        <v-icon start>mdi-arrow-left</v-icon>
        {{ $t('workflowDesigner.changeClient') }}
      </v-btn>

      <WorkflowDesigner
        ref="designerRef"
        :client-id="selectedClient.client_id"
        :client-name="selectedClient.client_name"
        @saved="handleSaved"
        @error="handleError"
      />
    </div>

    <!-- Snackbar -->
    <v-snackbar
      v-model="showSnackbar"
      :color="snackbarColor"
      :timeout="3000"
    >
      {{ snackbarMessage }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import WorkflowDesigner from '@/components/workflow/WorkflowDesigner.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// State
const clients = ref([])
const loadingClients = ref(false)
const selectedClientId = ref(null)
const selectedClient = ref(null)
const designerRef = ref(null)

// Snackbar state
const showSnackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

// Load clients on mount
onMounted(async () => {
  await loadClients()

  // Check if client_id is in route params
  if (route.params.clientId) {
    const clientId = parseInt(route.params.clientId)
    const client = clients.value.find(c => c.client_id === clientId)
    if (client) {
      selectedClientId.value = clientId
      selectedClient.value = client
    }
  }
})

const loadClients = async () => {
  try {
    loadingClients.value = true
    const response = await api.get('/api/clients')
    clients.value = response.data || []
  } catch (error) {
    console.error('Failed to load clients:', error)
    showNotification(t('errors.general'), 'error')
  } finally {
    loadingClients.value = false
  }
}

const handleClientSelect = (clientId) => {
  if (clientId) {
    const client = clients.value.find(c => c.client_id === clientId)
    if (client) {
      selectedClient.value = client
      // Update URL without full navigation
      router.replace({
        name: 'admin-workflow-designer',
        params: { clientId: clientId }
      })
    }
  } else {
    clearClient()
  }
}

const clearClient = () => {
  // Check for unsaved changes
  if (designerRef.value?.isDirty) {
    // The designer handles this with its own dialog
    return
  }

  selectedClientId.value = null
  selectedClient.value = null
  router.replace({ name: 'admin-workflow-designer' })
}

const handleSaved = () => {
  showNotification(t('success.saved'), 'success')
}

const handleError = (error) => {
  showNotification(error, 'error')
}

const showNotification = (message, color) => {
  snackbarMessage.value = message
  snackbarColor.value = color
  showSnackbar.value = true
}
</script>

<style scoped>
.workflow-designer-view {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
}

.designer-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
