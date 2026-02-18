<template>
  <v-row class="mt-4">
    <v-col cols="12" md="6">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2" size="small">mdi-chart-pie</v-icon>
          {{ $t('admin.workflowConfig.statusDistribution') }}
        </v-card-title>
        <v-card-text>
          <div v-if="loading" class="text-center py-4">
            <v-progress-circular indeterminate size="32" />
          </div>
          <div v-else-if="statusDistribution">
            <div
              v-for="item in statusDistribution.by_status"
              :key="item.status"
              class="d-flex align-center justify-space-between mb-2"
            >
              <v-chip :color="getStatusColor(item.status)" size="small" variant="tonal">
                {{ formatStatus(item.status) }}
              </v-chip>
              <div class="d-flex align-center">
                <v-progress-linear
                  :model-value="item.percentage"
                  :color="getStatusColor(item.status)"
                  height="8"
                  rounded
                  style="width: 100px;"
                  class="mr-2"
                />
                <span class="text-body-2 font-weight-medium" style="min-width: 80px;">
                  {{ item.count }} ({{ item.percentage.toFixed(1) }}%)
                </span>
              </div>
            </div>
            <v-divider class="my-3" />
            <div class="text-body-2 text-medium-emphasis">
              {{ $t('admin.workflowConfig.totalOrders') }}: <strong>{{ statusDistribution.total_work_orders }}</strong>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </v-col>
    <v-col cols="12" md="6">
      <v-card>
        <v-card-title>
          <v-icon class="mr-2" size="small">mdi-clock-fast</v-icon>
          {{ $t('admin.workflowConfig.averageTimes') }}
        </v-card-title>
        <v-card-text>
          <div v-if="loading" class="text-center py-4">
            <v-progress-circular indeterminate size="32" />
          </div>
          <div v-else-if="averageTimes">
            <v-list density="compact" class="bg-transparent">
              <v-list-item v-if="averageTimes.averages?.lifecycle_days != null">
                <template v-slot:prepend>
                  <v-icon size="small" color="primary">mdi-calendar-range</v-icon>
                </template>
                <v-list-item-title>{{ $t('admin.workflowConfig.avgLifecycle') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ averageTimes.averages.lifecycle_days.toFixed(1) }} {{ $t('common.days') }}</span>
                </template>
              </v-list-item>
              <v-list-item v-if="averageTimes.averages?.lead_time_hours != null">
                <template v-slot:prepend>
                  <v-icon size="small" color="info">mdi-inbox</v-icon>
                </template>
                <v-list-item-title>{{ $t('admin.workflowConfig.avgLeadTime') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ averageTimes.averages.lead_time_hours.toFixed(1) }} {{ $t('common.hours') }}</span>
                </template>
              </v-list-item>
              <v-list-item v-if="averageTimes.averages?.processing_time_hours != null">
                <template v-slot:prepend>
                  <v-icon size="small" color="success">mdi-factory</v-icon>
                </template>
                <v-list-item-title>{{ $t('admin.workflowConfig.avgProcessing') }}</v-list-item-title>
                <template v-slot:append>
                  <span class="font-weight-bold">{{ averageTimes.averages.processing_time_hours.toFixed(1) }} {{ $t('common.hours') }}</span>
                </template>
              </v-list-item>
            </v-list>
            <v-divider class="my-3" />
            <div class="text-body-2 text-medium-emphasis">
              {{ $t('admin.workflowConfig.sampleSize') }}: <strong>{{ averageTimes.count }}</strong>
            </div>
          </div>
          <v-alert v-else type="info" variant="tonal" density="compact">
            {{ $t('admin.workflowConfig.noAnalyticsData') }}
          </v-alert>
        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  statusDistribution: { type: Object, default: null },
  averageTimes: { type: Object, default: null },
  getStatusColor: { type: Function, required: true },
  formatStatus: { type: Function, required: true }
})
</script>
