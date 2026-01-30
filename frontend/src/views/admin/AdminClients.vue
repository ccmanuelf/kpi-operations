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
                  v-model="clientFormData.contact_name"
                  :label="t('admin.clients.contactName')"
                  prepend-icon="mdi-account"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.contact_email"
                  :label="t('admin.clients.contactEmail')"
                  prepend-icon="mdi-email"
                  :rules="[rules.email]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.contact_phone"
                  :label="t('admin.clients.contactPhone')"
                  prepend-icon="mdi-phone"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="clientFormData.industry"
                  :label="t('admin.clients.industry')"
                  prepend-icon="mdi-factory"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12">
                <v-textarea
                  v-model="clientFormData.address"
                  label="Address"
                  prepend-icon="mdi-map-marker"
                  variant="outlined"
                  density="comfortable"
                  rows="2"
                />
              </v-col>
              <v-col cols="12">
                <v-textarea
                  v-model="clientFormData.notes"
                  label="Notes"
                  prepend-icon="mdi-note-text"
                  variant="outlined"
                  density="comfortable"
                  rows="2"
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="clientDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="saveClient" :loading="saving" :disabled="!formValid">
            {{ editingClient ? 'Update' : 'Create' }}
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
              <v-list-item-title>Client ID</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.client_id }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.contact_name">
              <template v-slot:prepend>
                <v-icon>mdi-account</v-icon>
              </template>
              <v-list-item-title>Contact</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.contact_name }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.contact_email">
              <template v-slot:prepend>
                <v-icon>mdi-email</v-icon>
              </template>
              <v-list-item-title>Email</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.contact_email }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.contact_phone">
              <template v-slot:prepend>
                <v-icon>mdi-phone</v-icon>
              </template>
              <v-list-item-title>Phone</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.contact_phone }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.industry">
              <template v-slot:prepend>
                <v-icon>mdi-factory</v-icon>
              </template>
              <v-list-item-title>Industry</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.industry }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedClient.address">
              <template v-slot:prepend>
                <v-icon>mdi-map-marker</v-icon>
              </template>
              <v-list-item-title>Address</v-list-item-title>
              <v-list-item-subtitle>{{ selectedClient.address }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <template v-slot:prepend>
                <v-icon>mdi-calendar</v-icon>
              </template>
              <v-list-item-title>Created</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(selectedClient.created_at) }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="viewDialog = false">Close</v-btn>
          <v-btn color="primary" @click="viewDialog = false; editClient(selectedClient)">Edit</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon color="error" class="mr-2">mdi-alert</v-icon>
          Confirm Delete
        </v-card-title>
        <v-card-text>
          Are you sure you want to delete client <strong>{{ clientToDelete?.client_name }}</strong>?
          This will also remove all associated data.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">Cancel</v-btn>
          <v-btn color="error" @click="deleteClient" :loading="deleting">Delete</v-btn>
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

const { t } = useI18n()
import api from '@/services/api'

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
  contact_name: '',
  contact_email: '',
  contact_phone: '',
  industry: '',
  address: '',
  notes: ''
})

const headers = [
  { title: 'Client ID', key: 'client_id', sortable: true },
  { title: 'Client Name', key: 'client_name', sortable: true },
  { title: 'Contact', key: 'contact_name', sortable: true },
  { title: 'Email', key: 'contact_email', sortable: true },
  { title: 'Industry', key: 'industry', sortable: true },
  { title: 'Status', key: 'is_active', sortable: true },
  { title: 'Created', key: 'created_at', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
]

const statusOptions = [
  { title: 'Active', value: true },
  { title: 'Inactive', value: false }
]

const rules = {
  required: v => !!v || 'This field is required',
  email: v => !v || /.+@.+\..+/.test(v) || 'Invalid email address'
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
  if (!date) return 'N/A'
  return new Date(date).toLocaleDateString()
}

const refreshClients = async () => {
  loading.value = true
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (error) {
    console.error('Failed to load clients:', error)
    showSnackbar('Failed to load clients', 'error')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  editingClient.value = null
  clientFormData.value = {
    client_id: '',
    client_name: '',
    contact_name: '',
    contact_email: '',
    contact_phone: '',
    industry: '',
    address: '',
    notes: ''
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
    contact_name: client.contact_name || '',
    contact_email: client.contact_email || '',
    contact_phone: client.contact_phone || '',
    industry: client.industry || '',
    address: client.address || '',
    notes: client.notes || ''
  }
  clientDialog.value = true
}

const saveClient = async () => {
  saving.value = true
  try {
    if (editingClient.value) {
      await api.updateClient(editingClient.value.client_id, clientFormData.value)
      showSnackbar('Client updated successfully')
    } else {
      await api.createClient(clientFormData.value)
      showSnackbar('Client created successfully')
    }
    clientDialog.value = false
    refreshClients()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || 'Failed to save client', 'error')
  } finally {
    saving.value = false
  }
}

const toggleClientStatus = async (client) => {
  try {
    await api.updateClient(client.client_id, { is_active: !client.is_active })
    showSnackbar(`Client ${client.is_active ? 'deactivated' : 'activated'} successfully`)
    refreshClients()
  } catch (error) {
    showSnackbar('Failed to update client status', 'error')
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
    showSnackbar('Client deleted successfully')
    deleteDialog.value = false
    refreshClients()
  } catch (error) {
    showSnackbar('Failed to delete client', 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  refreshClients()
})
</script>
