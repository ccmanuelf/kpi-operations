<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-4">
          <h1 class="text-h4">
            <v-icon class="mr-2">mdi-domain</v-icon>
            {{ t('admin.clients.title') }}
          </h1>
          <v-btn color="primary" @click="openCreateDialog">
            <v-icon left>mdi-plus</v-icon>
            {{ t('admin.clients.addClient') }}
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-row class="mb-4">
      <v-col cols="12" md="4">
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          :label="t('admin.clients.searchClients')"
          variant="outlined"
          density="comfortable"
          clearable
          hide-details
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-select
          v-model="statusFilter"
          :items="statusOptions"
          :label="t('admin.users.filterByStatus')"
          variant="outlined"
          density="comfortable"
          clearable
          hide-details
        />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn variant="outlined" @click="refreshClients" :loading="loading">
          <v-icon>mdi-refresh</v-icon>
        </v-btn>
      </v-col>
    </v-row>

    <!-- Clients Table -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="filteredClients"
        :loading="loading"
        :search="search"
        class="elevation-1"
        :no-data-text="t('common.noData')"
      >
        <template v-slot:item.is_active="{ item }">
          <v-chip :color="item.is_active ? 'success' : 'error'" size="small">
            {{ item.is_active ? t('admin.users.active') : t('admin.users.inactive') }}
          </v-chip>
        </template>

        <template v-slot:item.created_at="{ item }">
          {{ formatDate(item.created_at) }}
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn icon size="small" variant="text" @click="viewClient(item)">
            <v-icon>mdi-eye</v-icon>
          </v-btn>
          <v-btn icon size="small" variant="text" @click="editClient(item)">
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn icon size="small" variant="text" @click="toggleClientStatus(item)">
            <v-icon>{{ item.is_active ? 'mdi-close-circle' : 'mdi-check-circle' }}</v-icon>
          </v-btn>
          <v-btn icon size="small" variant="text" color="error" @click="confirmDelete(item)">
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </template>
      </v-data-table>
    </v-card>

    <!-- Create/Edit Client Dialog -->
    <v-dialog v-model="clientDialog" max-width="700">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">{{ editingClient ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          {{ editingClient ? t('admin.clients.editClient') : t('admin.clients.createClient') }}
        </v-card-title>
        <v-card-text>
          <v-form ref="clientForm" v-model="formValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.client_id"
                  :label="t('admin.clients.clientId')"
                  prepend-icon="mdi-identifier"
                  :rules="[rules.required]"
                  :disabled="!!editingClient"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.client_name"
                  :label="t('admin.clients.clientName')"
                  prepend-icon="mdi-domain"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.client_contact"
                  :label="t('admin.clients.contactName')"
                  prepend-icon="mdi-account"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.client_email"
                  :label="t('admin.clients.contactEmail')"
                  prepend-icon="mdi-email"
                  :rules="[rules.email]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.client_phone"
                  :label="t('admin.clients.contactPhone')"
                  prepend-icon="mdi-phone"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12">
                <v-text-field
                  v-model="clientFormData.location"
                  :label="t('admin.clients.location')"
                  prepend-icon="mdi-map-marker"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="clientDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="saveClient" :loading="saving" :disabled="!formValid">
            {{ editingClient ? t('common.update') : t('admin.clients.createClient') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- View Client Dialog -->
    <v-dialog v-model="viewDialog" max-width="600">
      <v-card v-if="selectedClient">
        <v-card-title>
          <v-icon class="mr-2">mdi-domain</v-icon>
          {{ selectedClient.client_name }}
        </v-card-title>
        <v-card-text>
          <v-list>
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-identifier</v-icon>
              </template>
              <v-list-item-title>{{ t('admin.clients.clientId') }}</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.client_id }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.client_contact">
              <template v-slot:prepend>
                <v-icon>mdi-account</v-icon>
              </template>
              <v-list-item-title>{{ t('admin.clients.contactName') }}</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.client_contact }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.client_email">
              <template v-slot:prepend>
                <v-icon>mdi-email</v-icon>
              </template>
              <v-list-item-title>{{ t('admin.clients.contactEmail') }}</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.client_email }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.client_phone">
              <template v-slot:prepend>
                <v-icon>mdi-phone</v-icon>
              </template>
              <v-list-item-title>{{ t('admin.clients.contactPhone') }}</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.client_phone }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.location">
              <template v-slot:prepend>
                <v-icon>mdi-map-marker</v-icon>
              </template>
              <v-list-item-title>{{ t('admin.clients.location') }}</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.location }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-calendar</v-icon>
              </template>
              <v-list-item-title>{{ t('admin.clients.created') }}</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(selectedClient.created_at) }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="viewDialog = false">{{ t('common.close') }}</v-btn>
          <v-btn color="primary" @click="viewDialog = false; editClient(selectedClient)">{{ t('common.edit') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon color="error" class="mr-2">mdi-alert</v-icon>
          {{ t('common.confirmDelete') }}
        </v-card-title>
        <v-card-text>
          {{ t('admin.clients.confirmDeleteMessage', { client: clientToDelete?.client_name }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" @click="deleteClient" :loading="deleting">{{ t('common.delete') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="3000">
      {{ snackbarMessage }}
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
import api from '@/services/api'
import { formatLocaleDateIntl } from '@/utils/localeDate'

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const search = ref('')
const statusFilter = ref(null)
const clients = ref([])

const clientDialog = ref(false)
const viewDialog = ref(false)
const deleteDialog = ref(false)
const editingClient = ref(null)
const selectedClient = ref(null)
const clientToDelete = ref(null)
const formValid = ref(false)

const snackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

const clientFormData = ref({
  client_id: '',
  client_name: '',
  client_contact: '',
  client_email: '',
  client_phone: '',
  location: ''
})

const headers = computed(() => [
  { title: t('admin.clients.clientId'), key: 'client_id', sortable: true },
  { title: t('admin.clients.clientName'), key: 'client_name', sortable: true },
  { title: t('admin.clients.contactName'), key: 'client_contact', sortable: true },
  { title: t('admin.clients.contactEmail'), key: 'client_email', sortable: true },
  { title: t('common.status'), key: 'is_active', sortable: true },
  { title: t('admin.clients.created'), key: 'created_at', sortable: true },
  { title: t('common.actions'), key: 'actions', sortable: false, align: 'center' }
])

const statusOptions = computed(() => [
  { title: t('admin.users.active'), value: true },
  { title: t('admin.users.inactive'), value: false }
])

const rules = {
  required: v => !!v || t('admin.clients.fieldRequired'),
  email: v => !v || /.+@.+\..+/.test(v) || t('admin.clients.invalidEmail')
}

const filteredClients = computed(() => {
  let result = clients.value
  if (statusFilter.value !== null) {
    result = result.filter(c => c.is_active === statusFilter.value)
  }
  return result
})

const showSnackbar = (message, color = 'success') => {
  snackbarMessage.value = message
  snackbarColor.value = color
  snackbar.value = true
}

const formatDate = (date) => {
  if (!date) return t('common.na')
  return formatLocaleDateIntl(new Date(date), locale.value)
}

const refreshClients = async () => {
  loading.value = true
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (error) {
    // eslint-disable-next-line no-console -- dev-only, gated by import.meta.env.DEV
    if (import.meta.env.DEV) console.error('Failed to load clients:', error)
    showSnackbar(t('admin.clients.failedToLoadClients'), 'error')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  editingClient.value = null
  clientFormData.value = {
    client_id: '',
    client_name: '',
    client_contact: '',
    client_email: '',
    client_phone: '',
    location: ''
  }
  clientDialog.value = true
}

const viewClient = (client) => {
  selectedClient.value = client
  viewDialog.value = true
}

const editClient = (client) => {
  editingClient.value = client
  clientFormData.value = {
    client_id: client.client_id,
    client_name: client.client_name,
    client_contact: client.client_contact || '',
    client_email: client.client_email || '',
    client_phone: client.client_phone || '',
    location: client.location || ''
  }
  clientDialog.value = true
}

const saveClient = async () => {
  saving.value = true
  try {
    if (editingClient.value) {
      await api.updateClient(editingClient.value.client_id, clientFormData.value)
      showSnackbar(t('admin.clients.clientUpdated'))
    } else {
      await api.createClient(clientFormData.value)
      showSnackbar(t('admin.clients.clientCreated'))
    }
    clientDialog.value = false
    refreshClients()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('admin.clients.failedToSaveClient'), 'error')
  } finally {
    saving.value = false
  }
}

const toggleClientStatus = async (client) => {
  try {
    await api.updateClient(client.client_id, { is_active: !client.is_active })
    showSnackbar(client.is_active ? t('admin.clients.clientDeactivated') : t('admin.clients.clientActivated'))
    refreshClients()
  } catch {
    showSnackbar(t('admin.clients.failedToUpdateStatus'), 'error')
  }
}

const confirmDelete = (client) => {
  clientToDelete.value = client
  deleteDialog.value = true
}

const deleteClient = async () => {
  deleting.value = true
  try {
    await api.deleteClient(clientToDelete.value.client_id)
    showSnackbar(t('admin.clients.clientDeleted'))
    deleteDialog.value = false
    refreshClients()
  } catch {
    showSnackbar(t('admin.clients.failedToDeleteClient'), 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  refreshClients()
})
</script>
