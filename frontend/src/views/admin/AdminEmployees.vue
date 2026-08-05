<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex justify-space-between align-center bg-primary">
            <div class="d-flex align-center">
              <v-icon class="mr-2">mdi-card-account-details-outline</v-icon>
              <span>{{ $t('admin.employees.title') }}</span>
            </div>
          </v-card-title>

          <v-card-text data-testid="admin-employees-content">
            <v-row class="mb-3">
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="search"
                  :label="$t('common.search')"
                  variant="outlined"
                  density="compact"
                  clearable
                  hide-details
                  prepend-inner-icon="mdi-magnify"
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-btn color="primary" :loading="loading" @click="fetchData">
                  <v-icon left>mdi-refresh</v-icon>
                  {{ $t('common.refresh') }}
                </v-btn>
              </v-col>
            </v-row>

            <AGGridBase
              :columnDefs="columnDefs"
              :rowData="filteredEmployees"
              height="560px"
              :pagination="true"
              :paginationPageSize="25"
              :enableExcelPaste="false"
              entry-type="production"
              @cell-value-changed="onCellValueChanged"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
/**
 * AdminEmployees — the Employees admin surface (Cycle 3 PR-A, Task 7).
 *
 * Previously missing: FloatingPoolManagement.vue's docstring and the
 * entry-surface audit both refer to an "employee admin" surface that
 * owns general Employee fields, but no frontend page implemented it —
 * only the floating-pool-scoped assignment grid existed. This view
 * fills that gap, scoped per YAGNI to what this task needs: a read-only
 * roster (employee_code/employee_name/department) plus the one editable
 * field required by the labor-hours-capture roadmap, labor_class
 * (direct/indirect/unclassified), via inline AG Grid edit — same
 * pattern as useFloatingPoolGridData's current_assignment column.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notificationStore'
import useEmployeeAdminGrid from '@/composables/useEmployeeAdminGrid'

const { t } = useI18n()
const notificationStore = useNotificationStore()
const loading = ref(false)
const search = ref('')
const employees = ref([])

const fetchData = async () => {
  loading.value = true
  try {
    const response = await api.get('/employees')
    employees.value = response.data || []
  } catch {
    notificationStore.showError(t('admin.employees.errors.loadFailed'))
  } finally {
    loading.value = false
  }
}

const { columnDefs, onCellValueChanged } = useEmployeeAdminGrid({
  fetchData,
  notify: notificationStore,
})

const filteredEmployees = computed(() => {
  const term = (search.value || '').trim().toLowerCase()
  if (!term) return employees.value
  return employees.value.filter(
    (e) =>
      String(e.employee_name || '').toLowerCase().includes(term) ||
      String(e.employee_code || '').toLowerCase().includes(term),
  )
})

onMounted(fetchData)
</script>
