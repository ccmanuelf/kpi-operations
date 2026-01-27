<template>
  <div class="alerts-view">
    <div class="page-header">
      <h1>Intelligent Alerts</h1>
      <p class="subtitle">Proactive monitoring and early warning system for KPI management</p>
    </div>
    <AlertDashboard />
  </div>
</template>

<script setup>
import AlertDashboard from '@/components/alerts/AlertDashboard.vue'
</script>

<style scoped>
.alerts-view {
  padding: 1.5rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h1 {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
}

.subtitle {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
}
</style>
