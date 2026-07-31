<template>
  <div class="not-found-view">
    <EmptyState
      variant="error"
      size="large"
      elevated
      :title="t('notFound.title')"
      :description="t('notFound.description')"
      :action-text="t('notFound.goHome')"
      action-icon="mdi-home"
      @action="goHome"
    />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import EmptyState from '@/components/ui/EmptyState.vue'

const { t } = useI18n()
const router = useRouter()

const goHome = () => {
  router.push('/')
}
</script>

<style scoped>
.not-found-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: 1.5rem;
}
</style>
