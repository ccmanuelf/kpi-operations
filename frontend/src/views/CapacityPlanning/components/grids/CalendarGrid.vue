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
      <v-btn size="small" variant="outlined" @click="generateMonth">
        <v-icon start>mdi-calendar-month</v-icon>
        {{ t('capacityPlanning.calendar.generateMonth') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <v-data-table
        :headers="headers"
        :items="calendar"
        :items-per-page="31"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:item.calendar_date="{ item, index }">
          <v-text-field
            v-model="item.calendar_date"
            type="date"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.is_working_day="{ item, index }">
          <v-checkbox
            v-model="item.is_working_day"
            hide-details
            density="compact"
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.shifts_available="{ item, index }">
          <v-select
            v-model.number="item.shifts_available"
            :items="[1, 2, 3]"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.shift1_hours="{ item, index }">
          <v-text-field
            v-model.number="item.shift1_hours"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.shift2_hours="{ item, index }">
          <v-text-field
            v-model.number="item.shift2_hours"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            :disabled="item.shifts_available < 2"
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.holiday_name="{ item, index }">
          <v-text-field
            v-model="item.holiday_name"
            density="compact"
            variant="plain"
            hide-details
            placeholder="(optional)"
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.actions="{ index }">
          <v-btn
            icon="mdi-delete"
            size="x-small"
            variant="text"
            color="error"
            @click="removeRow(index)"
          />
        </template>
      </v-data-table>

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
 * CalendarGrid - Editable grid for the master production calendar.
 *
 * Manages working day entries with date, working day flag, shifts available,
 * shift hours, and holiday names. Includes a "Generate Month" dialog that
 * auto-creates calendar entries for a selected year/month, marking weekends
 * as non-working days.
 *
 * Store dependency: useCapacityPlanningStore (worksheets.masterCalendar)
 * No props or emits -- all state managed via store.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const { t } = useI18n()
const store = useCapacityPlanningStore()

const showGenerateDialog = ref(false)
const generateYear = ref(new Date().getFullYear())
const generateMonthNum = ref(new Date().getMonth() + 1)

const headers = computed(() => [
  { title: t('capacityPlanning.calendar.headers.date'), key: 'calendar_date', width: '140px' },
  { title: t('capacityPlanning.calendar.headers.workingDay'), key: 'is_working_day', width: '100px' },
  { title: t('capacityPlanning.calendar.headers.shifts'), key: 'shifts_available', width: '80px' },
  { title: t('capacityPlanning.calendar.headers.shift1Hours'), key: 'shift1_hours', width: '100px' },
  { title: t('capacityPlanning.calendar.headers.shift2Hours'), key: 'shift2_hours', width: '100px' },
  { title: t('capacityPlanning.calendar.headers.holiday'), key: 'holiday_name', width: '150px' },
  { title: t('capacityPlanning.calendar.headers.actions'), key: 'actions', width: '80px', sortable: false }
])

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
  { text: t('capacityPlanning.calendar.months.december'), value: 12 }
])

const calendar = computed(() => store.worksheets.masterCalendar.data)

const addRow = () => store.addRow('masterCalendar')
const removeRow = (index) => store.removeRow('masterCalendar', index)
const markDirty = () => {
  store.worksheets.masterCalendar.dirty = true
}

const generateMonth = () => {
  showGenerateDialog.value = true
}

const doGenerateMonth = () => {
  const year = generateYear.value
  const month = generateMonthNum.value
  const daysInMonth = new Date(year, month, 0).getDate()

  const entries = []
  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(year, month - 1, day)
    const dayOfWeek = date.getDay()
    const isWeekend = dayOfWeek === 0 || dayOfWeek === 6

    entries.push({
      calendar_date: date.toISOString().slice(0, 10),
      is_working_day: !isWeekend,
      shifts_available: 1,
      shift1_hours: isWeekend ? 0 : 8.0,
      shift2_hours: 0,
      shift3_hours: 0,
      holiday_name: null,
      notes: null
    })
  }

  store.importData('masterCalendar', entries)
  showGenerateDialog.value = false
}
</script>
