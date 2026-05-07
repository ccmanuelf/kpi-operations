<template>
  <v-container fluid data-testid="attendance-entry-view">
    <v-row>
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center mb-4">
          <h1 class="text-h3">{{ t('navigation.attendanceEntry') }}</h1>
          <CSVUploadDialogAttendance />
        </div>
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12">
        <AttendanceEntryGrid />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AttendanceEntryGrid from '@/components/grids/AttendanceEntryGrid.vue'
import CSVUploadDialogAttendance from '@/components/CSVUploadDialogAttendance.vue'

const { t } = useI18n()
</script>
