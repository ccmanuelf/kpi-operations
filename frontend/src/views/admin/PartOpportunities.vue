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
        <v-btn
          color="purple"
          prepend-icon="mdi-help-circle"
          variant="outlined"
          @click="showGuide = true"
        >
          {{ $t('admin.floatingPool.howToUse') }}
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
                {{ item.complexity || $t('common.standard') }}
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
                  :hint="$t('admin.hintPartNumber')"
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

    <!-- How-to Guide Dialog -->
    <PartOpportunitiesGuide v-model="showGuide" />

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
import { onMounted, ref } from 'vue'
import { usePartOpportunitiesData } from '@/composables/usePartOpportunitiesData'
import { usePartOpportunitiesForms } from '@/composables/usePartOpportunitiesForms'
import PartOpportunitiesGuide from './components/PartOpportunitiesGuide.vue'

// Guide dialog
const showGuide = ref(false)

// Data composable
const {
  loading,
  selectedClient,
  partOpportunities,
  search,
  snackbar,
  clientOptions,
  averageOpportunities,
  minOpportunities,
  maxOpportunities,
  headers,
  getOpportunityColor,
  getComplexityColor,
  loadClients,
  loadPartOpportunities,
  showSnackbar
} = usePartOpportunitiesData()

// Forms composable
const {
  editDialog,
  uploadDialog,
  deleteDialog,
  isEditing,
  deleteTarget,
  saving,
  uploading,
  deleting,
  form,
  formValid,
  formData,
  uploadFile,
  replaceExisting,
  complexityOptions,
  rules,
  openCreateDialog,
  openEditDialog,
  closeEditDialog,
  savePartOpportunity,
  confirmDelete,
  deletePartOpportunity,
  openUploadDialog,
  closeUploadDialog,
  uploadCSV,
  downloadTemplate
} = usePartOpportunitiesForms(selectedClient, loadPartOpportunities, showSnackbar)

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
