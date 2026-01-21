import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue')
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/production-entry',
      name: 'production-entry',
      component: () => import('@/views/ProductionEntry.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi-dashboard',
      name: 'kpi-dashboard',
      component: () => import('@/views/KPIDashboard.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/efficiency',
      name: 'kpi-efficiency',
      component: () => import('@/views/kpi/Efficiency.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/wip-aging',
      name: 'kpi-wip-aging',
      component: () => import('@/views/kpi/WIPAging.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/on-time-delivery',
      name: 'kpi-on-time-delivery',
      component: () => import('@/views/kpi/OnTimeDelivery.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/availability',
      name: 'kpi-availability',
      component: () => import('@/views/kpi/Availability.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/performance',
      name: 'kpi-performance',
      component: () => import('@/views/kpi/Performance.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/quality',
      name: 'kpi-quality',
      component: () => import('@/views/kpi/Quality.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/absenteeism',
      name: 'kpi-absenteeism',
      component: () => import('@/views/kpi/Absenteeism.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/kpi/oee',
      name: 'kpi-oee',
      component: () => import('@/views/kpi/OEE.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/data-entry/downtime',
      name: 'downtime-entry',
      component: () => import('@/components/entries/DowntimeEntry.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/data-entry/attendance',
      name: 'attendance-entry',
      component: () => import('@/components/entries/AttendanceEntry.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/data-entry/quality',
      name: 'quality-entry',
      component: () => import('@/components/entries/QualityEntry.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/data-entry/hold-resume',
      name: 'hold-resume-entry',
      component: () => import('@/components/entries/HoldResumeEntry.vue'),
      meta: { requiresAuth: true }
    },
    // Admin Routes
    {
      path: '/admin/settings',
      name: 'admin-settings',
      component: () => import('@/views/admin/AdminSettings.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('@/views/admin/AdminUsers.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/admin/clients',
      name: 'admin-clients',
      component: () => import('@/views/admin/AdminClients.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    },
    {
      path: '/admin/defect-types',
      name: 'admin-defect-types',
      component: () => import('@/views/admin/AdminDefectTypes.vue'),
      meta: { requiresAuth: true, requiresAdmin: true }
    }
  ]
})

// Navigation guard - check auth from localStorage directly to avoid Pinia timing issues
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('access_token')
  const isAuthenticated = !!token

  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router
