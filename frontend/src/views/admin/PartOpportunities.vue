<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-2">
          <v-icon class="mr-2">mdi-chart-scatter-plot</v-icon>
          {{ $t('admin.partOpportunities') }}
        </h1>
        <p class="text-subtitle-1 text-grey">
          {{ $t('admin.partOpportunitiesDescription') }}
        </p>
      </v-col>
    </v-row>

    <!-- Info Card -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-alert type="info" variant="tonal" density="compact">
          <v-icon class="mr-2">mdi-information</v-icon>
          {{ $t('admin.partOpportunitiesInfo') }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Actions and Filters -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clientOptions"
          item-title="client_name"
          item-value="client_id"
          :label="$t('filters.client')"
          variant="outlined"
          density="comfortable"
          prepend-inner-icon="mdi-domain"
          clearable
          @update:model-value="loadPartOpportunities"
        />
      </v-col>
      <v-col cols="12" md="8" class="d-flex align-center gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="openCreateDialog"
        >
          {{ $t('admin.addPartOpportunity') }}
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-upload"
          @click="openUploadDialog"
        >
          {{ $t('csv.upload') }}
        </v-btn>
        <v-btn
          color="info"
          prepend-icon="mdi-download"
          variant="outlined"
          @click="downloadTemplate"
        >
          {{ $t('csv.downloadTemplate') }}
        </v-btn>
        <v-spacer />
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          :label="$t('common.search')"
          single-line
          hide-details
          density="compact"
          variant="outlined"
          style="max-width: 250px"
        />
      </v-col>
    </v-row>

    <!-- Summary Stats -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="primary">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ partOpportunities.length }}</div>
            <div class="text-caption">{{ $t('admin.totalParts') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="info">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ averageOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.avgOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="success">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ minOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.minOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="tonal" color="warning">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ maxOpportunities }}</div>
            <div class="text-caption">{{ $t('admin.maxOpportunities') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Part Opportunities Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-data-table
            :headers="headers"
            :items="partOpportunities"
            :search="search"
            :loading="loading"
            :items-per-page="15"
            class="elevation-0"
          >
            <template v-slot:item.part_number="{ item }">
              <span class="font-weight-medium text-primary">{{ item.part_number }}</span>
            </template>

            <template v-slot:item.opportunities_per_unit="{ item }">
              <v-chip
                :color="getOpportunityColor(item.opportunities_per_unit)"
                size="small"
              >
                {{ item.opportunities_per_unit }}
              </v-chip>
            </template>

            <template v-slot:item.complexity="{ item }">
              <v-chip
                :color="getComplexityColor(item.complexity)"
                size="small"
                variant="tonal"
              >
                {{ item.complexity || 'Standard' }}
              </v-chip>
            </template>

            <template v-slot:item.is_active="{ item }">
              <v-icon :color="item.is_active !== false ? 'success' : 'grey'">
                {{ item.is_active !== false ? 'mdi-check-circle' : 'mdi-close-circle' }}
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
                <v-icon size="48" color="grey">mdi-chart-scatter-plot</v-icon>
                <p class="mt-2 text-grey">{{ $t('admin.noPartOpportunities') }}</p>
                <v-btn color="primary" class="mt-2" @click="openCreateDialog">
                  {{ $t('admin.addPartOpportunity') }}
                </v-btn>
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
          {{ isEditing ? $t('admin.editPartOpportunity') : $t('admin.addPartOpportunity') }}
        </v-card-title>
        <v-card-text>
          <v-form ref="form" v-model="formValid">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.part_number"
                  :label="$t('jobs.partNumber') + ' *'"
                  :rules="[rules.required, rules.maxLength50]"
                  variant="outlined"
                  density="comfortable"
                  :disabled="isEditing"
                  hint="e.g., PART-001, SKU-12345"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="formData.opportunities_per_unit"
                  :label="$t('admin.opportunitiesPerUnit') + ' *'"
                  type="number"
                  :rules="[rules.required, rules.positive]"
                  variant="outlined"
                  density="comfortable"
                  :hint="$t('admin.opportunitiesHint')"
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="formData.part_description"
                  :label="$t('admin.partDescription')"
                  variant="outlined"
                  density="comfortable"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.complexity"
                  :items="complexityOptions"
                  :label="$t('admin.complexity')"
                  variant="outlined"
                  density="comfortable"
                  clearable
                />
              </v-col>
            </v-row>
            <v-row>
              <v-col cols="12" md="6">
                <v-select
                  v-model="formData.client_id"
                  :items="clientOptions"
                  item-title="client_name"
                  item-value="client_id"
                  :label="$t('filters.client')"
                  variant="outlined"
                  density="comfortable"
                  :disabled="isEditing"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-textarea
                  v-model="formData.notes"
                  :label="$t('production.notes')"
                  variant="outlined"
                  density="comfortable"
                  rows="2"
                />
              </v-col>
            </v-row>
            <v-row v-if="isEditing">
              <v-col cols="12">
                <v-switch
                  v-model="formData.is_active"
                  :label="$t('common.active')"
                  color="success"
                  hide-details
                />
              </v-col>
            </v-row>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeEditDialog">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!formValid"
            @click="savePartOpportunity"
          >
            {{ isEditing ? $t('common.update') : $t('common.save') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Upload CSV Dialog -->
    <v-dialog v-model="uploadDialog" max-width="500" persistent>
      <v-card>
        <v-card-title>
          <v-icon class="mr-2">mdi-upload</v-icon>
          {{ $t('csv.uploadPartOpportunities') }}
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            {{ $t('csv.partOpportunitiesInfo') }}
          </v-alert>
          <v-file-input
            v-model="uploadFile"
            :label="$t('csv.selectFile')"
            accept=".csv"
            prepend-icon="mdi-file-delimited"
            variant="outlined"
            show-size
          />
          <v-checkbox
            v-model="replaceExisting"
            :label="$t('csv.replaceExisting')"
            :hint="$t('csv.replaceExistingHint')"
            persistent-hint
            color="warning"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeUploadDialog">{{ $t('common.cancel') }}</v-btn>
          <v-btn
            color="primary"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadCSV"
          >
            {{ $t('csv.upload') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="400">
      <v-card>
        <v-card-title class="text-error">
          <v-icon class="mr-2">mdi-alert</v-icon>
          {{ $t('common.confirmDelete') }}
        </v-card-title>
        <v-card-text>
          {{ $t('admin.deletePartOpportunityConfirm', { part: deleteTarget?.part_number }) }}
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="error" :loading="deleting" @click="deletePartOpportunity">
            {{ $t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">{{ $t('common.close') }}</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

const { t } = useI18n()

// State
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const deleting = ref(false)
const clients = ref([])
const selectedClient = ref(null)
const partOpportunities = ref([])
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
  part_number: '',
  opportunities_per_unit: 10,
  part_description: '',
  complexity: '',
  client_id: null,
  notes: '',
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
const complexityOptions = ['Simple', 'Standard', 'Complex', 'Very Complex']

// Validation rules
const rules = {
  required: v => !!v || t('validation.required'),
  maxLength50: v => !v || v.length <= 50 || t('validation.maxLength', { max: 50 }),
  positive: v => (v && v > 0) || t('validation.positive')
}

// Computed
const clientOptions = computed(() => {
  return [{ client_id: null, client_name: t('common.all') }, ...clients.value]
})

const averageOpportunities = computed(() => {
  if (partOpportunities.value.length === 0) return 0
  const sum = partOpportunities.value.reduce((acc, p) => acc + (p.opportunities_per_unit || 0), 0)
  return Math.round(sum / partOpportunities.value.length)
})

const minOpportunities = computed(() => {
  if (partOpportunities.value.length === 0) return 0
  return Math.min(...partOpportunities.value.map(p => p.opportunities_per_unit || 0))
})

const maxOpportunities = computed(() => {
  if (partOpportunities.value.length === 0) return 0
  return Math.max(...partOpportunities.value.map(p => p.opportunities_per_unit || 0))
})

const headers = computed(() => [
  { title: t('jobs.partNumber'), key: 'part_number', sortable: true },
  { title: t('admin.partDescription'), key: 'part_description', sortable: true },
  { title: t('admin.opportunitiesPerUnit'), key: 'opportunities_per_unit', sortable: true },
  { title: t('admin.complexity'), key: 'complexity', sortable: true },
  { title: t('common.active'), key: 'is_active', sortable: true },
  { title: t('common.actions'), key: 'actions', sortable: false, align: 'end' }
])

// Methods
const getOpportunityColor = (count) => {
  if (count <= 5) return 'success'
  if (count <= 15) return 'info'
  if (count <= 30) return 'warning'
  return 'error'
}

const getComplexityColor = (complexity) => {
  switch (complexity) {
    case 'Simple': return 'success'
    case 'Standard': return 'info'
    case 'Complex': return 'warning'
    case 'Very Complex': return 'error'
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

const loadPartOpportunities = async () => {
  loading.value = true
  try {
    const params = {}
    if (selectedClient.value) {
      params.client_id = selectedClient.value
    }
    const res = await api.get('/part-opportunities', { params })
    partOpportunities.value = res.data || []
  } catch (error) {
    console.error('Failed to load part opportunities:', error)
    partOpportunities.value = []
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  isEditing.value = false
  formData.value = {
    part_number: '',
    opportunities_per_unit: 10,
    part_description: '',
    complexity: 'Standard',
    client_id: selectedClient.value,
    notes: '',
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

const savePartOpportunity = async () => {
  if (!formValid.value) return

  saving.value = true
  try {
    if (isEditing.value) {
      await api.put(`/part-opportunities/${formData.value.part_opportunities_id}`, formData.value)
      showSnackbar(t('success.updated'), 'success')
    } else {
      await api.post('/part-opportunities', formData.value)
      showSnackbar(t('success.saved'), 'success')
    }
    closeEditDialog()
    await loadPartOpportunities()
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

const deletePartOpportunity = async () => {
  if (!deleteTarget.value) return

  deleting.value = true
  try {
    await api.delete(`/part-opportunities/${deleteTarget.value.part_opportunities_id}`)
    showSnackbar(t('success.deleted'), 'success')
    deleteDialog.value = false
    await loadPartOpportunities()
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
  if (!uploadFile.value) return

  uploading.value = true
  try {
    const formDataUpload = new FormData()
    formDataUpload.append('file', uploadFile.value)
    formDataUpload.append('replace_existing', replaceExisting.value)
    if (selectedClient.value) {
      formDataUpload.append('client_id', selectedClient.value)
    }

    const res = await api.post('/part-opportunities/upload', formDataUpload, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    showSnackbar(t('csv.success', { count: res.data.created || 0 }), 'success')
    closeUploadDialog()
    await loadPartOpportunities()
  } catch (error) {
    showSnackbar(error.response?.data?.detail || t('csv.error'), 'error')
  } finally {
    uploading.value = false
  }
}

const downloadTemplate = () => {
  const headers = ['part_number', 'opportunities_per_unit', 'part_description', 'complexity', 'notes']
  const example = ['PART-001', '15', 'Standard T-Shirt', 'Standard', 'Basic garment']
  const csv = [headers.join(','), example.join(',')].join('\n')

  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'part_opportunities_template.csv'
  a.click()
  URL.revokeObjectURL(url)

  showSnackbar(t('success.downloaded'), 'success')
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

onMounted(() => {
  loadClients()
  loadPartOpportunities()
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
