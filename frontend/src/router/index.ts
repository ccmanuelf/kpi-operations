import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    requiresAdmin?: boolean
  }
}

interface StoredUser {
  role?: string
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/production-entry',
    name: 'production-entry',
    component: () => import('@/views/ProductionEntry.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi-dashboard',
    name: 'kpi-dashboard',
    component: () => import('@/views/KPIDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/efficiency',
    name: 'kpi-efficiency',
    component: () => import('@/views/kpi/Efficiency.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/wip-aging',
    name: 'kpi-wip-aging',
    component: () => import('@/views/kpi/WIPAging.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/on-time-delivery',
    name: 'kpi-on-time-delivery',
    component: () => import('@/views/kpi/OnTimeDelivery.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/availability',
    name: 'kpi-availability',
    component: () => import('@/views/kpi/Availability.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/performance',
    name: 'kpi-performance',
    component: () => import('@/views/kpi/Performance.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/quality',
    name: 'kpi-quality',
    component: () => import('@/views/kpi/Quality.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/absenteeism',
    name: 'kpi-absenteeism',
    component: () => import('@/views/kpi/Absenteeism.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/kpi/oee',
    name: 'kpi-oee',
    component: () => import('@/views/kpi/OEE.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/data-entry/downtime',
    name: 'downtime-entry',
    component: () => import('@/components/entries/DowntimeEntry.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/data-entry/attendance',
    name: 'attendance-entry',
    component: () => import('@/components/entries/AttendanceEntry.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/data-entry/quality',
    name: 'quality-entry',
    component: () => import('@/views/QualityEntry.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/data-entry/hold-resume',
    name: 'hold-resume-entry',
    component: () => import('@/views/HoldResumeEntry.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/work-orders',
    name: 'work-orders',
    component: () => import('@/views/WorkOrderManagement.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/my-shift',
    name: 'my-shift',
    component: () => import('@/views/MyShiftDashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('@/views/AlertsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/simulation',
    name: 'simulation',
    component: () => import('@/views/SimulationV2View.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/simulation-v2',
    redirect: '/simulation',
  },
  {
    path: '/plan-vs-actual',
    name: 'plan-vs-actual',
    component: () => import('@/views/PlanVsActualView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/capacity-planning',
    name: 'capacity-planning',
    component: () => import('@/views/CapacityPlanning/CapacityPlanningView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin/settings',
    name: 'admin-settings',
    component: () => import('@/views/admin/AdminSettings.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/users',
    name: 'admin-users',
    component: () => import('@/views/admin/AdminUsers.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/clients',
    name: 'admin-clients',
    component: () => import('@/views/admin/AdminClients.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/defect-types',
    name: 'admin-defect-types',
    component: () => import('@/views/admin/AdminDefectTypes.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/part-opportunities',
    name: 'admin-part-opportunities',
    component: () => import('@/views/admin/PartOpportunities.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/client-config',
    name: 'admin-client-config',
    component: () => import('@/views/admin/ClientConfigView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/floating-pool',
    name: 'admin-floating-pool',
    component: () => import('@/views/admin/FloatingPoolManagement.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/workflow-config',
    name: 'admin-workflow-config',
    component: () => import('@/views/admin/WorkflowConfigView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/workflow-designer/:clientId?',
    name: 'admin-workflow-designer',
    component: () => import('@/views/admin/WorkflowDesignerView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/database',
    name: 'admin-database',
    component: () => import('@/views/admin/DatabaseConfigView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/variance-report',
    name: 'admin-variance-report',
    component: () => import('@/views/admin/AssumptionVarianceReport.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

const readStoredUser = (): StoredUser | null => {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null') as StoredUser | null
  } catch {
    return null
  }
}

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  const isAuthenticated = !!token

  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
    return
  }

  if (to.meta.requiresAdmin && isAuthenticated) {
    const user = readStoredUser()
    const isAdmin = user?.role === 'admin' || user?.role === 'ADMIN'
    if (!isAdmin) {
      next('/')
      return
    }
  }

  if (to.path === '/login' && isAuthenticated) {
    const user = readStoredUser()
    const landing: Record<string, string> = {
      operator: '/my-shift',
      leader: '/',
      poweruser: '/capacity-planning',
      admin: '/kpi-dashboard',
    }
    const role = user?.role
    next((role && landing[role]) || '/')
    return
  }

  next()
})

export default router
