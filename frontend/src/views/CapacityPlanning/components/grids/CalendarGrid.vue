<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-calendar</v-icon>
      {{ t('capacityPlanning.calendar.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" class="mr-2" @click="addRow">
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.calendar.addDate') }}
      </v-btn>
      <v-btn size="small" variant="outlined" @click="showGenerateDialog = true">
        <v-icon start>mdi-calendar-month</v-icon>
        {{ t('capacityPlanning.calendar.generateMonth') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <AGGridBase
        :columnDefs="columnDefs"
        :rowData="calendar"
        height="600px"
        :pagination="true"
        :paginationPageSize="31"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onCellValueChanged"
      />

      <div v-if="!calendar.length" class="text-center pa-4 text-grey">
        {{ t('capacityPlanning.calendar.noData') }}
      </div>
    </v-card-text>

    <!-- Generate Month Dialog -->
    <v-dialog v-model="showGenerateDialog" max-width="400">
      <v-card>
        <v-card-title>{{ t('capacityPlanning.calendar.generateMonthlyCalendar') }}</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="generateYear"
            :label="t('common.year')"
            type="number"
            variant="outlined"
            class="mb-2"
          />
          <v-select
            v-model="generateMonthNum"
            :items="monthOptions"
            item-title="text"
            item-value="value"
            :label="t('common.month')"
            variant="outlined"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showGenerateDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="doGenerateMonth">{{ t('capacityPlanning.calendar.generateMonth') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * CalendarGrid - AG Grid surface for the master production calendar.
 *
 * Migrated 2026-05-01 from v-data-table + per-cell v-text-field/v-select
 * slots to AGGridBase as part of Group D Surface #12 of the
 * entry-interface audit.
 *
 * Preserves the "Generate Month" dialog UX (year + month picker auto-
 * populates the worksheet with weekday/weekend defaults). shift2_hours
 * column editable only when shifts_available >= 2 (matches legacy
 * conditional :disabled binding).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import useCalendarGridData from '@/composables/useCalendarGridData'

const { t } = useI18n()

const showGenerateDialog = ref(false)
const generateYear = ref(new Date().getFullYear())
const generateMonthNum = ref(new Date().getMonth() + 1)

const monthOptions = computed(() => [
  { text: t('capacityPlanning.calendar.months.january'), value: 1 },
  { text: t('capacityPlanning.calendar.months.february'), value: 2 },
  { text: t('capacityPlanning.calendar.months.march'), value: 3 },
  { text: t('capacityPlanning.calendar.months.april'), value: 4 },
  { text: t('capacityPlanning.calendar.months.may'), value: 5 },
  { text: t('capacityPlanning.calendar.months.june'), value: 6 },
  { text: t('capacityPlanning.calendar.months.july'), value: 7 },
  { text: t('capacityPlanning.calendar.months.august'), value: 8 },
  { text: t('capacityPlanning.calendar.months.september'), value: 9 },
  { text: t('capacityPlanning.calendar.months.october'), value: 10 },
  { text: t('capacityPlanning.calendar.months.november'), value: 11 },
  { text: t('capacityPlanning.calendar.months.december'), value: 12 },
])

const {
  calendar,
  columnDefs,
  addRow,
  onCellValueChanged,
  importGeneratedMonth,
} = useCalendarGridData()

const doGenerateMonth = () => {
  importGeneratedMonth(Number(generateYear.value), Number(generateMonthNum.value))
  showGenerateDialog.value = false
}
</script>
