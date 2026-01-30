<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-alert-circle-outline</v-icon>
          {{ t('admin.defectTypes.title') }}
        </h1>
        <p class="text-subtitle-1 text-grey">
          {{ t('admin.defectTypes.subtitle') }}
        </p>
      </v-col>
    </v-row>

    <!-- Client Selector and Actions -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clientOptions"
          item-title="client_name"
          item-value="client_id"
          :label="t('admin.defectTypes.selectClientOrGlobal')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          @update:model-value="loadDefectTypes"
        >
          <template v-slot:item="{ props, item }">
            <v-list-item v-bind="props">
              <template v-slot:prepend>
                <v-icon :color="item.raw.client_id === GLOBAL_CLIENT_ID ? 'primary' : ''">
                  {{ item.raw.client_id === GLOBAL_CLIENT_ID ? 'mdi-earth' : 'mdi-domain' }}
                </v-icon>
              </template>
            </v-list-item>
          </template>
        </v-select>
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          :disabled="!selectedClient"
          @click="openCreateDialog"
        >
          {{ t('admin.defectTypes.addDefectType') }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-upload"
          :disabled="!selectedClient"
          @click="openUploadDialog"
        >
          {{ t('admin.defectTypes.uploadCsv') }}
        </v-btn>
        <v-btn
          color="info"
          prepend-icon="mdi-download"
          variant="outlined"
          @click="downloadTemplate"
        >
          {{ t('admin.defectTypes.downloadTemplate') }}
        </v-btn>
        <v-spacer />
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          :label="t('common.search')"
          single-line
          hide-details
          density="compact"
          variant="outlined"
          style="max-width: 250px"
        />
      </v-col>
    </v-row>

    <!-- Client Info Card -->
    <v-row v-if="selectedClientInfo" class="mt-2">
      <v-col cols="12">
        <v-alert
          :type="isGlobalSelected ? 'warning' : 'info'"
          variant="tonal"
          density="compact"
        >
          <template v-slot:prepend>
            <v-icon>{{ isGlobalSelected ? 'mdi-earth' : 'mdi-domain' }}</v-icon>
          </template>
          <strong>{{ selectedClientInfo.client_name }}</strong> -
          {{ defectTypes.length }} {{ t('admin.defectTypes.defectTypesConfigured') }}
          <span v-if="isGlobalSelected" class="ml-2 text-caption">
            ({{ t('admin.defectTypes.availableToAllClients') }})
          </span>
        </v-alert>
      </v-col>
    </v-row>

    <!-- Defect Types Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-data-table
            :headers="headers"
            :items="defectTypes"
            :search="search"
            :loading="loading"
            :items-per-page="15"
            class="elevation-0"
          >
            <template v-slot:item.severity_default="{ item }">
              <v-chip
                :color="getSeverityColor(item.severity_default)"
                size="small"
                variant="tonal"
              >
                {{ item.severity_default }}
              </v-chip>
            </template>
            <template v-slot:item.category="{ item }">
              <v-chip size="small" variant="outlined">
                {{ item.category || t('admin.defectTypes.uncategorized') }}
              </v-chip>
            </template>
            <template v-slot:item.is_active="{ item }">
              <v-icon :color="item.is_active ? 'success' : 'grey'">
                {{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}
              </v-icon>
            </template>
            <template v-slot:item.actions="{ item }">
              <v-btn
                icon="mdi-pencil"
                size="small"
                variant="text"
                color="primary"
                @click="openEditDialog(item)"
              />
              <v-btn
                icon="mdi-delete"
                size="small"
                variant="text"
                color="error"
                @click="confirmDelete(item)"
              />
            </template>
            <template v-slot:no-data>
              <div class="text-center pa-4">
                <v-icon size="48" color="grey">mdi-alert-circle-outline</v-icon>
                <p class="mt-2 text-grey">
                  {{ selectedClient ? t('admin.defectTypes.noDefectTypesForClient') : t('admin.defectTypes.selectClientToView') }}
                </p>
              </div>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Create/Edit Dialog -->
    <v-dialog v-model="editDialog" max-width="600" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">{{ isEditing ? 'mdi-pencil' : 'mdi-plus' }}</v-icon>
          {{ isEditing ? t('admin.defectTypes.editDefectType') : t('admin.defectTypes.addDefectType') }}
        </v-card-title>
        <v-card-text>
          <v-form ref="form" v-model="formValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.defect_code"
                  :label="t('admin.defectTypes.defectCode') + ' *'"
                  :rules="[rules.required, rules.maxLength20]"
                  variant="outlined"
                  density="comfortable"
                  hint="Short code (e.g., SOLDER_DEF)"
                  :disabled="isEditing"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.defect_name"
                  :label="t('admin.defectTypes.defectName') + ' *'"
                  :rules="[rules.required, rules.maxLength100]"
                  variant="outlined"
                  density="comfortable"
                  hint="Display name (e.g., Solder Defect)"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12">
                <v-textarea
                  v-model="formData.description"
                  :label="t('admin.defectTypes.description')"
                  variant="outlined"
                  density="comfortable"
                  rows="2"
                  hint="Detailed description for training/reference"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.category"
                  :items="categories"
                  :label="t('admin.defectTypes.category')"
                  variant="outlined"
                  density="comfortable"
                  clearable
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.severity_default"
                  :items="severities"
                  :label="t('admin.defectTypes.defaultSeverity') + ' *'"
                  :rules="[rules.required]"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.industry_standard_code"
                  :label="t('admin.defectTypes.industryStandardCode')"
                  variant="outlined"
                  density="comfortable"
                  hint="e.g., IPC-A-610-5.2"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.sort_order"
                  :label="t('admin.defectTypes.sortOrder')"
                  type="number"
                  variant="outlined"
                  density="comfortable"
                  hint="Display order (0-999)"
                />
              </v-col>
            </v-row>
            <v-row v-if="isEditing">
              <v-col cols="12">
                <v-switch
                  v-model="formData.is_active"
                  :label="t('common.active')"
                  color="success"
                  hide-details
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeEditDialog">{{ t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!formValid"
            @click="saveDefectType"
          >
            {{ isEditing ? t('common.update') : t('common.create') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Upload CSV Dialog -->
    <v-dialog v-model="uploadDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-upload</v-icon>
          {{ t('admin.defectTypes.uploadDefectTypesCsv') }}
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            Upload a CSV file to bulk import defect types for <strong>{{ selectedClientInfo?.client_name }}</strong>
          </v-alert>
          <v-file-input
            v-model="uploadFile"
            :label="t('admin.defectTypes.selectCsvFile')"
            accept=".csv"
            prepend-icon="mdi-file-delimited"
            variant="outlined"
            show-size
          />
          <v-checkbox
            v-model="replaceExisting"
            :label="t('admin.defectTypes.replaceExisting')"
            :hint="t('admin.defectTypes.replaceExistingHint')"
            persistent-hint
            color="warning"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeUploadDialog">{{ t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadCSV"
          >
            {{ t('common.upload') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ t('admin.defectTypes.confirmDelete') }}
        </v-card-title>
        <v-card-text>
          {{ t('admin.defectTypes.confirmDeleteMessage') }}
          <strong>"{{ deleteTarget?.defect_name }}"</strong>?
          <p class="mt-2 text-grey">{{ t('admin.defectTypes.deleteNote') }}</p>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="deleteDefectType">
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">{{ t('common.close') }}</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import api from '@/services/api'

// Global constant
const GLOBAL_CLIENT_ID = 'GLOBAL'

// State
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const deleting = ref(false)
const clients = ref([])
const selectedClient = ref(null)
const defectTypes = ref([])
const search = ref('')

// Dialogs
const editDialog = ref(false)
const uploadDialog = ref(false)
const deleteDialog = ref(false)
const isEditing = ref(false)
const deleteTarget = ref(null)

// Form
const form = ref(null)
const formValid = ref(false)
const formData = ref({
  defect_code: '',
  defect_name: '',
  description: '',
  category: '',
  severity_default: 'MAJOR',
  industry_standard_code: '',
  sort_order: 0,
  is_active: true
})

// Upload
const uploadFile = ref(null)
const replaceExisting = ref(false)

// Snackbar
const snackbar = ref({
  show: false,
  message: '',
  color: 'success'
})

// Options
const severities = ['CRITICAL', 'MAJOR', 'MINOR']
const categories = [
  'Assembly',
  'Material',
  'Process',
  'Electrical',
  'Finish',
  'Measurement',
  'Sewing',
  'Packaging',
  'Labeling',
  'Cleanliness',
  'Testing',
  'Documentation',
  'Handling',
  'Environment',
  'General'
]

// Validation rules
const rules = {
  required: v => !!v || 'Required',
  maxLength20: v => !v || v.length <= 20 || 'Max 20 characters',
  maxLength100: v => !v || v.length <= 100 || 'Max 100 characters'
}

// Table headers
const headers = [
  { title: 'Code', key: 'defect_code', sortable: true },
  { title: 'Name', key: 'defect_name', sortable: true },
  { title: 'Category', key: 'category', sortable: true },
  { title: 'Severity', key: 'severity_default', sortable: true },
  { title: 'Standard', key: 'industry_standard_code', sortable: true },
  { title: 'Order', key: 'sort_order', sortable: true },
  { title: 'Active', key: 'is_active', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' }
]

// Computed
const clientOptions = computed(() => {
  // Add Global option at the top
  const globalOption = {
    client_id: GLOBAL_CLIENT_ID,
    client_name: t('admin.defectTypes.globalAllClients')
  }
  return [globalOption, ...clients.value]
})

const isGlobalSelected = computed(() => {
  return selectedClient.value === GLOBAL_CLIENT_ID
})

const selectedClientInfo = computed(() => {
  if (isGlobalSelected.value) {
    return { client_id: GLOBAL_CLIENT_ID, client_name: t('admin.defectTypes.globalAllClients') }
  }
  return clients.value.find(c => c.client_id === selectedClient.value)
})

// Methods
const getSeverityColor = (severity) => {
  switch (severity) {
    case 'CRITICAL': return 'error'
    case 'MAJOR': return 'warning'
    case 'MINOR': return 'info'
    default: return 'grey'
  }
}

const loadClients = async () => {
  try {
    const res = await api.getClients()
    clients.value = res.data || []
  } catch (error) {
    showSnackbar(t('errors.general'), 'error')
  }
}

const loadDefectTypes = async () => {
  if (!selectedClient.value) {
    defectTypes.value = []
    return
  }

  loading.value = true
  try {
    // When viewing a specific client, don't include global types (they're managed separately)
    // When viewing GLOBAL, only show global types
    const includeGlobal = false  // Don't mix global with client-specific in admin view
    const res = await api.getDefectTypesByClient(selectedClient.value, false, includeGlobal)
    defectTypes.value = res.data || []
  } catch (error) {
    showSnackbar(t('errors.general'), 'error')
    defectTypes.value = []
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEditing.value = false
  formData.value = {
    defect_code: '',
    defect_name: '',
    description: '',
    category: '',
    severity_default: 'MAJOR',
    industry_standard_code: '',
    sort_order: defectTypes.value.length + 1,
    is_active: true
  }
  editDialog.value = true
}

const openEditDialog = (item) => {
  isEditing.value = true
  formData.value = { ...item }
  editDialog.value = true
}

const closeEditDialog = () => {
  editDialog.value = false
  form.value?.reset()
}

const saveDefectType = async () => {
  if (!formValid.value) return

  saving.value = true
  try {
    if (isEditing.value) {
      await api.updateDefectType(formData.value.defect_type_id, formData.value)
      showSnackbar(t('admin.defectTypes.defectTypeUpdated'), 'success')
    } else {
      await api.createDefectType({
        ...formData.value,
        client_id: selectedClient.value
      })
      showSnackbar(t('admin.defectTypes.defectTypeCreated'), 'success')
    }
    closeEditDialog()
    await loadDefectTypes()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
  } finally {
    saving.value = false
  }
}

const confirmDelete = (item) => {
  deleteTarget.value = item
  deleteDialog.value = true
}

const deleteDefectType = async () => {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    await api.deleteDefectType(deleteTarget.value.defect_type_id)
    showSnackbar(t('admin.defectTypes.defectTypeDeleted'), 'success')
    deleteDialog.value = false
    await loadDefectTypes()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
  } finally {
    deleting.value = false
  }
}

const openUploadDialog = () => {
  uploadFile.value = null
  replaceExisting.value = false
  uploadDialog.value = true
}

const closeUploadDialog = () => {
  uploadDialog.value = false
  uploadFile.value = null
}

const uploadCSV = async () => {
  if (!uploadFile.value || !selectedClient.value) return

  uploading.value = true
  try {
    const res = await api.uploadDefectTypes(
      selectedClient.value,
      uploadFile.value,
      replaceExisting.value
    )
    showSnackbar(
      `${t('admin.defectTypes.uploadComplete')}: ${res.data.created} ${t('admin.defectTypes.created')}, ${res.data.skipped} ${t('admin.defectTypes.skipped')}`,
      'success'
    )
    closeUploadDialog()
    await loadDefectTypes()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('errors.general'), 'error')
  } finally {
    uploading.value = false
  }
}

const downloadTemplate = async () => {
  try {
    const res = await api.getDefectTypeTemplate()
    const template = res.data

    // Create CSV content
    const headers = template.template.columns.join(',')
    const rows = template.template.example_rows.map(row =>
      template.template.columns.map(col => {
        const val = row[col] || ''
        return val.includes(',') ? `"${val}"` : val
      }).join(',')
    )
    const csv = [headers, ...rows].join('\n')

    // Download
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'defect_types_template.csv'
    a.click()
    URL.revokeObjectURL(url)

    showSnackbar(t('admin.defectTypes.templateDownloaded'), 'success')
  } catch (error) {
    showSnackbar(t('errors.general'), 'error')
  }
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

onMounted(() => {
  loadClients()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
