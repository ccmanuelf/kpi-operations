# Manufacturing KPI Platform - Frontend Architecture

**Version:** 1.0
**Date:** 2025-12-31
**Author:** System Architect
**Status:** Phase 1 MVP Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Component Architecture](#component-architecture)
5. [State Management](#state-management)
6. [Routing & Navigation](#routing--navigation)
7. [Data Entry Workflows](#data-entry-workflows)
8. [KPI Dashboard Design](#kpi-dashboard-design)
9. [Responsive Design](#responsive-design)
10. [Build & Deployment](#build--deployment)

---

## Overview

### Design Philosophy
1. **User-Centric:** Minimize clicks, maximize Excel familiarity
2. **Tablet-First:** Optimized for shop floor tablets (10-12 inch screens)
3. **Offline-Ready:** Local storage for unreliable connections (Phase 2)
4. **Verification:** Mandatory read-back protocol prevents errors
5. **Performance:** Sub-second response for all operations

### Key Features
- **Excel-Like Grid:** Copy/paste from Excel directly into data entry grid
- **CSV Upload:** Drag-and-drop file upload with real-time validation
- **Read-Back Confirmation:** Every data entry requires explicit confirmation
- **Real-Time KPIs:** Live dashboard updates every 30 seconds
- **Multi-Language:** English/Spanish support (Phase 2)

---

## Technology Stack

### Core Framework
- **Vue.js 3.4+** (Composition API)
- **Vite 5.0+** (Build tool - fast HMR)
- **TypeScript 5.3+** (Type safety)

### UI Components
- **Vuetify 3.5+** (Material Design 3 components)
  - VDataTable for production grids
  - VDialog for read-back confirmations
  - VBtn, VCard, VTextField, etc.
- **Tailwind CSS 3.4+** (Utility-first styling)
  - Custom responsive breakpoints
  - Dark mode support (Phase 2)

### State Management
- **Pinia 2.1+** (Vue official state management)
  - KPI store (caching, real-time updates)
  - User/auth store (JWT token management)
  - Production entry store (local draft saving)

### Data Handling
- **Axios 1.6+** (HTTP client)
- **Day.js 1.11+** (Date/time manipulation)
- **PapaParse 5.4+** (CSV parsing)
- **ExcelJS 4.4+** (Excel import/export)

### Charts & Visualization
- **Chart.js 4.4+** with vue-chartjs (KPI trends)
- **ApexCharts 3.45+** (Advanced dashboards - Phase 2)

### Authentication
- **Vue Router 4.2+** (Route guards)
- **JWT Decode 4.0+** (Token parsing)

### Development Tools
- **ESLint 8.56+** (Code linting)
- **Prettier 3.1+** (Code formatting)
- **Vitest 1.1+** (Unit testing)
- **Cypress 13.6+** (E2E testing)

---

## Project Structure

```
frontend/
├── public/
│   ├── favicon.ico
│   └── logo.png
├── src/
│   ├── assets/                    # Static assets
│   │   ├── images/
│   │   └── styles/
│   │       ├── variables.css      # CSS custom properties
│   │       └── tailwind.css       # Tailwind base
│   ├── components/                # Reusable components
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── AppFooter.vue
│   │   │   └── LoadingSpinner.vue
│   │   ├── data-entry/
│   │   │   ├── DataEntryGrid.vue          # ⭐ Excel-like grid
│   │   │   ├── ReadBackConfirm.vue        # ⭐ Verification dialog
│   │   │   ├── CsvUploader.vue            # ⭐ Drag-drop CSV
│   │   │   └── ValidationErrors.vue
│   │   ├── kpi/
│   │   │   ├── KpiCard.vue                # Single KPI display
│   │   │   ├── KpiTrendChart.vue          # 30-day trend line
│   │   │   ├── EfficiencyGauge.vue        # Circular gauge
│   │   │   └── PerformanceChart.vue       # Bar chart
│   │   └── reports/
│   │       ├── ReportPreview.vue
│   │       └── EmailScheduler.vue
│   ├── views/                     # Page components
│   │   ├── LoginView.vue
│   │   ├── DashboardView.vue              # KPI overview
│   │   ├── ProductionEntryView.vue        # ⭐ Main data entry
│   │   ├── WorkOrderListView.vue
│   │   ├── ReportsView.vue
│   │   └── AdminView.vue
│   ├── stores/                    # Pinia stores
│   │   ├── auth.ts                        # User authentication
│   │   ├── kpi.ts                         # KPI calculations
│   │   ├── production.ts                  # Production entries
│   │   └── workOrder.ts                   # Work order management
│   ├── router/
│   │   └── index.ts                       # Route definitions + guards
│   ├── services/                  # API service layer
│   │   ├── api.ts                         # Axios instance + interceptors
│   │   ├── authService.ts
│   │   ├── productionService.ts
│   │   ├── kpiService.ts
│   │   └── reportService.ts
│   ├── composables/               # Reusable composition functions
│   │   ├── useAuth.ts
│   │   ├── useKpi.ts
│   │   ├── useValidation.ts
│   │   └── useExcelPaste.ts               # ⭐ Excel copy/paste logic
│   ├── types/                     # TypeScript interfaces
│   │   ├── production.ts
│   │   ├── workOrder.ts
│   │   ├── kpi.ts
│   │   └── user.ts
│   ├── utils/                     # Utility functions
│   │   ├── formatters.ts                  # Date, number, currency
│   │   ├── validators.ts                  # Field validation
│   │   └── inference.ts                   # Client-side inference hints
│   ├── App.vue                    # Root component
│   ├── main.ts                    # Application entry
│   └── vite-env.d.ts              # Vite type declarations
├── .env.development               # Development environment
├── .env.production                # Production environment
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── README.md
```

---

## Component Architecture

### Core Components (Phase 1 MVP)

#### 1. **DataEntryGrid.vue** ⭐
**Purpose:** Excel-like grid for production data entry
**Features:**
- Copy/paste from Excel (preserves multi-cell selection)
- Inline validation (red border for errors)
- Add/remove rows dynamically
- Auto-save drafts to localStorage every 30s
- Keyboard navigation (Tab, Enter, Arrow keys)

**Props:**
```typescript
interface DataEntryGridProps {
  clientId: string;
  shiftDate: string;
  shiftType: 'SHIFT_1ST' | 'SHIFT_2ND' | 'SAT_OT' | 'SUN_OT' | 'OTHER';
  mode: 'create' | 'edit';
}
```

**Component Structure:**
```vue
<template>
  <v-card>
    <v-card-title>
      Production Entry Grid
      <v-chip color="info" class="ml-2">{{ draftRows.length }} rows</v-chip>
    </v-card-title>

    <v-card-text>
      <!-- Grid Header -->
      <v-data-table
        :headers="headers"
        :items="draftRows"
        item-key="tempId"
        class="excel-grid"
        density="compact"
        :loading="isLoading"
      >
        <!-- Custom cell templates -->
        <template #item.work_order_id="{ item }">
          <v-text-field
            v-model="item.work_order_id"
            density="compact"
            variant="outlined"
            :error-messages="getErrorMessage(item, 'work_order_id')"
            @blur="validateField(item, 'work_order_id')"
          />
        </template>

        <template #item.units_produced="{ item }">
          <v-text-field
            v-model.number="item.units_produced"
            type="number"
            density="compact"
            variant="outlined"
            :error-messages="getErrorMessage(item, 'units_produced')"
          />
        </template>

        <!-- ... more columns ... -->

        <template #item.actions="{ item }">
          <v-btn
            icon="mdi-delete"
            size="small"
            color="error"
            @click="removeRow(item)"
          />
        </template>
      </v-data-table>
    </v-card-text>

    <v-card-actions>
      <v-btn prepend-icon="mdi-plus" @click="addRow">Add Row</v-btn>
      <v-btn prepend-icon="mdi-content-paste" @click="pasteFromExcel">
        Paste from Excel
      </v-btn>
      <v-spacer />
      <v-btn color="primary" size="large" @click="submitBatch">
        Submit All ({{ draftRows.length }} rows)
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { ProductionEntry } from '@/types/production';
import { useExcelPaste } from '@/composables/useExcelPaste';
import { useValidation } from '@/composables/useValidation';

const props = defineProps<DataEntryGridProps>();
const emit = defineEmits<{
  submit: [entries: ProductionEntry[]];
}>();

const draftRows = ref<ProductionEntry[]>([]);
const { parseExcelClipboard } = useExcelPaste();
const { validateProductionEntry } = useValidation();

// Headers configuration
const headers = [
  { title: 'Work Order ID', key: 'work_order_id', width: 180 },
  { title: 'Units Produced', key: 'units_produced', width: 140 },
  { title: 'Units Defective', key: 'units_defective', width: 140 },
  { title: 'Run Time (hrs)', key: 'run_time_hours', width: 120 },
  { title: 'Employees', key: 'employees_assigned', width: 100 },
  { title: 'Notes', key: 'notes', width: 200 },
  { title: 'Actions', key: 'actions', width: 80, sortable: false },
];

// Auto-save drafts every 30 seconds
let autoSaveInterval: number;
onMounted(() => {
  loadDrafts();
  autoSaveInterval = window.setInterval(saveDrafts, 30000);
});

onUnmounted(() => {
  clearInterval(autoSaveInterval);
});

// Excel paste handler
async function pasteFromExcel() {
  try {
    const clipboardData = await navigator.clipboard.readText();
    const parsedRows = parseExcelClipboard(clipboardData);

    // Validate and add to grid
    parsedRows.forEach(row => {
      draftRows.value.push({
        ...row,
        tempId: crypto.randomUUID(),
        shift_date: props.shiftDate,
        shift_type: props.shiftType,
      });
    });
  } catch (error) {
    console.error('Paste failed:', error);
  }
}

function submitBatch() {
  // Trigger read-back confirmation
  emit('submit', draftRows.value);
}
</script>

<style scoped>
.excel-grid :deep(.v-data-table__td) {
  padding: 4px 8px;
}

.excel-grid :deep(.v-text-field) {
  font-size: 14px;
}
</style>
```

---

#### 2. **ReadBackConfirm.vue** ⭐
**Purpose:** Mandatory verification dialog before saving data
**Features:**
- Displays all entries in readable format
- Highlights potential issues (negative values, missing fields)
- "Confirm All" or "Edit Individual" options
- Cannot be bypassed (enforced by business logic)

**Component Structure:**
```vue
<template>
  <v-dialog v-model="isOpen" max-width="800" persistent>
    <v-card>
      <v-card-title class="bg-primary text-white">
        <v-icon>mdi-clipboard-check</v-icon>
        Confirm Production Entries
      </v-card-title>

      <v-card-text class="pt-4">
        <v-alert type="warning" variant="tonal" class="mb-4">
          Please review these {{ entries.length }} entries before submitting.
          Once confirmed, data will be saved to the database.
        </v-alert>

        <v-list>
          <v-list-item
            v-for="(entry, index) in entries"
            :key="index"
            class="border-b"
          >
            <v-list-item-title class="font-weight-bold">
              Entry #{{ index + 1 }}: {{ entry.work_order_id }}
            </v-list-item-title>
            <v-list-item-subtitle>
              <div class="mt-2">
                <v-chip size="small" class="mr-2">
                  {{ entry.units_produced }} units produced
                </v-chip>
                <v-chip
                  size="small"
                  :color="entry.units_defective > 0 ? 'warning' : 'success'"
                  class="mr-2"
                >
                  {{ entry.units_defective }} defective
                </v-chip>
                <v-chip size="small" class="mr-2">
                  {{ entry.run_time_hours }} hrs run time
                </v-chip>
                <v-chip size="small">
                  {{ entry.employees_assigned }} employees
                </v-chip>
              </div>
              <div v-if="entry.notes" class="mt-2 text-caption">
                Notes: {{ entry.notes }}
              </div>
            </v-list-item-subtitle>

            <template #append>
              <v-btn
                icon="mdi-pencil"
                size="small"
                variant="text"
                @click="editEntry(index)"
              />
            </template>
          </v-list-item>
        </v-list>

        <v-alert v-if="inferenceWarnings.length > 0" type="info" class="mt-4">
          <strong>Inference Applied:</strong>
          <ul class="mt-2">
            <li v-for="warning in inferenceWarnings" :key="warning">
              {{ warning }}
            </li>
          </ul>
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn @click="cancel">Cancel</v-btn>
        <v-spacer />
        <v-btn color="primary" size="large" @click="confirmAll">
          Confirm All {{ entries.length }} Entries
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { ProductionEntry } from '@/types/production';

const props = defineProps<{
  entries: ProductionEntry[];
  modelValue: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  confirm: [entries: ProductionEntry[]];
  edit: [index: number];
}>();

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
});

const inferenceWarnings = computed(() => {
  const warnings: string[] = [];
  props.entries.forEach((entry, idx) => {
    if (!entry.ideal_cycle_time) {
      warnings.push(`Entry #${idx + 1}: Using default cycle time (0.25 hrs)`);
    }
  });
  return warnings;
});

function confirmAll() {
  emit('confirm', props.entries);
  isOpen.value = false;
}

function editEntry(index: number) {
  emit('edit', index);
}

function cancel() {
  isOpen.value = false;
}
</script>
```

---

#### 3. **CsvUploader.vue** ⭐
**Purpose:** Drag-and-drop CSV file upload with validation
**Features:**
- Drag-and-drop or click to browse
- Real-time CSV parsing and validation
- Error display (row-by-row breakdown)
- Download error report CSV
- Template download link

**Component Structure:**
```vue
<template>
  <v-card>
    <v-card-title>CSV Batch Upload</v-card-title>

    <v-card-text>
      <!-- Drop Zone -->
      <div
        class="drop-zone"
        :class="{ 'drop-zone--active': isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <v-icon size="64" color="primary">mdi-cloud-upload</v-icon>
        <p class="text-h6 mt-4">Drag & Drop CSV File Here</p>
        <p class="text-caption">or</p>
        <v-btn color="primary" @click="triggerFileInput">Browse Files</v-btn>
        <input
          ref="fileInput"
          type="file"
          accept=".csv"
          hidden
          @change="handleFileSelect"
        />
      </div>

      <!-- Template Download -->
      <v-alert type="info" class="mt-4">
        <v-icon>mdi-information</v-icon>
        First time? Download the CSV template to see the correct format.
        <v-btn
          variant="text"
          prepend-icon="mdi-download"
          class="ml-2"
          @click="downloadTemplate"
        >
          Download Template
        </v-btn>
      </v-alert>

      <!-- Validation Results -->
      <v-card v-if="validationResult" class="mt-4" variant="outlined">
        <v-card-title>
          <v-icon :color="validationResult.valid_rows > 0 ? 'success' : 'error'">
            {{ validationResult.valid_rows > 0 ? 'mdi-check-circle' : 'mdi-alert-circle' }}
          </v-icon>
          Validation Results
        </v-card-title>

        <v-card-text>
          <v-row>
            <v-col cols="4">
              <v-chip color="info" block>
                Total Rows: {{ validationResult.total_rows }}
              </v-chip>
            </v-col>
            <v-col cols="4">
              <v-chip color="success" block>
                Valid: {{ validationResult.valid_rows }}
              </v-chip>
            </v-col>
            <v-col cols="4">
              <v-chip color="error" block>
                Invalid: {{ validationResult.invalid_rows }}
              </v-chip>
            </v-col>
          </v-row>

          <!-- Error Details -->
          <v-expansion-panels v-if="validationResult.errors.length > 0" class="mt-4">
            <v-expansion-panel>
              <v-expansion-panel-title>
                View {{ validationResult.errors.length }} Errors
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-list density="compact">
                  <v-list-item
                    v-for="error in validationResult.errors"
                    :key="`${error.row}-${error.field}`"
                  >
                    <v-list-item-title>
                      Row {{ error.row }}, Field: {{ error.field }}
                    </v-list-item-title>
                    <v-list-item-subtitle class="text-error">
                      {{ error.error }}
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <v-btn
            v-if="validationResult.errors.length > 0"
            prepend-icon="mdi-download"
            class="mt-4"
            @click="downloadErrors"
          >
            Download Error Report
          </v-btn>
        </v-card-text>

        <v-card-actions>
          <v-btn @click="validationResult = null">Cancel</v-btn>
          <v-spacer />
          <v-btn
            color="primary"
            :disabled="validationResult.valid_rows === 0"
            @click="proceedWithValidRows"
          >
            Proceed with {{ validationResult.valid_rows }} Valid Rows
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Papa from 'papaparse';
import type { ProductionEntry } from '@/types/production';
import { productionService } from '@/services/productionService';

const isDragging = ref(false);
const fileInput = ref<HTMLInputElement>();
const validationResult = ref<any>(null);

function triggerFileInput() {
  fileInput.value?.click();
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files && target.files.length > 0) {
    parseAndValidate(target.files[0]);
  }
}

function handleDrop(event: DragEvent) {
  isDragging.value = false;
  if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
    parseAndValidate(event.dataTransfer.files[0]);
  }
}

async function parseAndValidate(file: File) {
  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,
    complete: async (results) => {
      // Send to backend for validation
      try {
        const response = await productionService.uploadBatch(results.data);
        validationResult.value = response.data;
      } catch (error) {
        console.error('Validation failed:', error);
      }
    },
    error: (error) => {
      console.error('Parse error:', error);
    },
  });
}

function downloadTemplate() {
  const csvContent = [
    'work_order_id,shift_date,shift_type,units_produced,units_defective,run_time_hours,employees_assigned,notes',
    '2025-12-15-BOOT-ABC123,2025-12-15,SHIFT_1ST,100,2,8.5,10,Example entry',
  ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'production_entry_template.csv';
  link.click();
}

function downloadErrors() {
  if (!validationResult.value) return;

  const errorCsv = [
    'row,field,error',
    ...validationResult.value.errors.map((e: any) =>
      `${e.row},${e.field},"${e.error}"`
    ),
  ].join('\n');

  const blob = new Blob([errorCsv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'validation_errors.csv';
  link.click();
}

function proceedWithValidRows() {
  // Emit valid rows to parent for read-back confirmation
  emit('validRowsReady', validationResult.value.valid_rows);
}

const emit = defineEmits<{
  validRowsReady: [rows: ProductionEntry[]];
}>();
</script>

<style scoped>
.drop-zone {
  border: 2px dashed rgb(var(--v-theme-primary));
  border-radius: 8px;
  padding: 48px;
  text-align: center;
  transition: all 0.3s ease;
  cursor: pointer;
}

.drop-zone--active {
  background-color: rgba(var(--v-theme-primary), 0.1);
  border-color: rgb(var(--v-theme-success));
}
</style>
```

---

#### 4. **KpiCard.vue**
**Purpose:** Display single KPI metric with trend indicator
**Features:**
- Large number display
- Trend arrow (up/down)
- Color coding (green = good, red = bad)
- Target comparison
- Click to view details

```vue
<template>
  <v-card class="kpi-card" @click="showDetails">
    <v-card-title class="text-caption text-grey">
      {{ title }}
    </v-card-title>

    <v-card-text>
      <div class="d-flex align-center">
        <div class="text-h3" :class="valueColor">
          {{ formattedValue }}
          <span class="text-h6 text-grey">{{ unit }}</span>
        </div>
        <v-icon
          v-if="trend !== 0"
          :icon="trend > 0 ? 'mdi-trending-up' : 'mdi-trending-down'"
          :color="trendColor"
          size="large"
          class="ml-2"
        />
      </div>

      <div v-if="target" class="mt-2 text-caption">
        Target: {{ target }}{{ unit }}
        <v-chip
          size="x-small"
          :color="varianceColor"
          class="ml-2"
        >
          {{ variance > 0 ? '+' : '' }}{{ variance.toFixed(1) }}%
        </v-chip>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  title: string;
  value: number;
  unit: string;
  target?: number;
  trend: number; // -1, 0, 1
  goodDirection: 'up' | 'down';
}>();

const emit = defineEmits<{
  details: [];
}>();

const formattedValue = computed(() => {
  return props.value.toFixed(1);
});

const valueColor = computed(() => {
  if (!props.target) return 'text-primary';

  const isAboveTarget = props.value >= props.target;
  const isGood = props.goodDirection === 'up' ? isAboveTarget : !isAboveTarget;

  return isGood ? 'text-success' : 'text-error';
});

const variance = computed(() => {
  if (!props.target) return 0;
  return ((props.value - props.target) / props.target) * 100;
});

const varianceColor = computed(() => {
  if (variance.value === 0) return 'grey';

  const isGood = props.goodDirection === 'up'
    ? variance.value > 0
    : variance.value < 0;

  return isGood ? 'success' : 'error';
});

const trendColor = computed(() => {
  const isGood = props.goodDirection === 'up'
    ? props.trend > 0
    : props.trend < 0;

  return isGood ? 'success' : 'error';
});

function showDetails() {
  emit('details');
}
</script>

<style scoped>
.kpi-card {
  cursor: pointer;
  transition: transform 0.2s ease;
}

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}
</style>
```

---

## State Management (Pinia Stores)

### KPI Store (stores/kpi.ts)
```typescript
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { kpiService } from '@/services/kpiService';
import type { KpiData, KpiFilter } from '@/types/kpi';

export const useKpiStore = defineStore('kpi', () => {
  // State
  const efficiencyData = ref<KpiData | null>(null);
  const performanceData = ref<KpiData | null>(null);
  const allKpisData = ref<any | null>(null);
  const isLoading = ref(false);
  const lastUpdated = ref<Date | null>(null);

  // Cache TTL (5 minutes)
  const CACHE_TTL = 5 * 60 * 1000;

  // Computed
  const isCacheValid = computed(() => {
    if (!lastUpdated.value) return false;
    return Date.now() - lastUpdated.value.getTime() < CACHE_TTL;
  });

  // Actions
  async function fetchEfficiency(filter: KpiFilter) {
    if (isCacheValid.value && efficiencyData.value) {
      return efficiencyData.value;
    }

    isLoading.value = true;
    try {
      const response = await kpiService.getEfficiency(filter);
      efficiencyData.value = response.data;
      lastUpdated.value = new Date();
      return response.data;
    } catch (error) {
      console.error('Failed to fetch efficiency:', error);
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchPerformance(filter: KpiFilter) {
    isLoading.value = true;
    try {
      const response = await kpiService.getPerformance(filter);
      performanceData.value = response.data;
      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  async function fetchAllKpis(filter: KpiFilter) {
    isLoading.value = true;
    try {
      const response = await kpiService.getAllKpis(filter);
      allKpisData.value = response.data;
      lastUpdated.value = new Date();
      return response.data;
    } finally {
      isLoading.value = false;
    }
  }

  function invalidateCache() {
    lastUpdated.value = null;
  }

  return {
    // State
    efficiencyData,
    performanceData,
    allKpisData,
    isLoading,
    lastUpdated,

    // Computed
    isCacheValid,

    // Actions
    fetchEfficiency,
    fetchPerformance,
    fetchAllKpis,
    invalidateCache,
  };
});
```

---

## Routing & Navigation

### Router Configuration (router/index.ts)
```typescript
import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true, roles: ['OPERATOR_DATAENTRY', 'LEADER_DATACONFIG', 'POWERUSER', 'ADMIN'] },
  },
  {
    path: '/production-entry',
    name: 'ProductionEntry',
    component: () => import('@/views/ProductionEntryView.vue'),
    meta: { requiresAuth: true, roles: ['OPERATOR_DATAENTRY', 'LEADER_DATACONFIG', 'POWERUSER', 'ADMIN'] },
  },
  {
    path: '/work-orders',
    name: 'WorkOrders',
    component: () => import('@/views/WorkOrderListView.vue'),
    meta: { requiresAuth: true, roles: ['LEADER_DATACONFIG', 'POWERUSER', 'ADMIN'] },
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/views/ReportsView.vue'),
    meta: { requiresAuth: true, roles: ['POWERUSER', 'ADMIN'] },
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/views/AdminView.vue'),
    meta: { requiresAuth: true, roles: ['ADMIN'] },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Navigation guards
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } });
  } else if (to.meta.roles && !authStore.hasRole(to.meta.roles as string[])) {
    next({ name: 'Dashboard' }); // Redirect to dashboard if insufficient permissions
  } else {
    next();
  }
});

export default router;
```

---

## Responsive Design

### Breakpoints (Tailwind Config)
```javascript
module.exports = {
  theme: {
    extend: {
      screens: {
        'tablet': '768px',   // Shop floor tablets
        'desktop': '1024px', // Office desktops
      },
    },
  },
};
```

### Mobile-First Grid
- **Tablet (768px+):** 2-column KPI layout
- **Desktop (1024px+):** 4-column KPI layout
- **Sidebar:** Collapsible on tablet, always visible on desktop

---

## Build & Deployment

### Development
```bash
npm run dev        # Start dev server (http://localhost:5173)
npm run lint       # Run ESLint
npm run test:unit  # Run Vitest unit tests
npm run test:e2e   # Run Cypress E2E tests
```

### Production Build
```bash
npm run build      # Build for production (dist/)
npm run preview    # Preview production build locally
```

### Environment Variables
```env
# .env.production
VITE_API_BASE_URL=https://api.manufacturing-kpi.com/api/v1
VITE_AUTH_TOKEN_KEY=mfg_kpi_token
VITE_REFRESH_TOKEN_KEY=mfg_kpi_refresh
VITE_CACHE_TTL=300000
```

---

**End of Frontend Architecture**
