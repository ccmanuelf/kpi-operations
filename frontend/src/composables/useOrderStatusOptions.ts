/**
 * Shared factory for work-order / order status option lists.
 * Returns a computed array of { title, value } pairs so the labels
 * stay reactive to locale changes (LanguageToggle / i18n).
 *
 * Consumers: usePlanVsActual, useWorkOrderData, WorkOrderDetailDrawer.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

export interface OrderStatusOption {
  title: string
  value: string
}

/** Options for the Plan-vs-Actual order-status filter (PENDING…CANCELLED). */
export function useOrderStatusOptions() {
  const { t } = useI18n()
  return computed<OrderStatusOption[]>(() => [
    { title: t('workOrders.status.pending'), value: 'PENDING' },
    { title: t('workOrders.status.inProgress'), value: 'IN_PROGRESS' },
    { title: t('workOrders.status.completed'), value: 'COMPLETED' },
    { title: t('workOrders.status.onHold'), value: 'ON_HOLD' },
    { title: t('workOrders.status.cancelled'), value: 'CANCELLED' },
  ])
}

/** Options for the Work-Order management status filter (ACTIVE…CANCELLED). */
export function useWorkOrderStatusOptions() {
  const { t } = useI18n()
  return computed<OrderStatusOption[]>(() => [
    { title: t('workOrders.status.active'), value: 'ACTIVE' },
    { title: t('workOrders.status.onHold'), value: 'ON_HOLD' },
    { title: t('workOrders.status.completed'), value: 'COMPLETED' },
    { title: t('workOrders.status.rejected'), value: 'REJECTED' },
    { title: t('workOrders.status.cancelled'), value: 'CANCELLED' },
  ])
}

/** Options for the Work-Order priority filter. */
export function useWorkOrderPriorityOptions() {
  const { t } = useI18n()
  return computed<OrderStatusOption[]>(() => [
    { title: t('workOrders.priorityLabel.urgent'), value: 'URGENT' },
    { title: t('workOrders.priorityLabel.high'), value: 'HIGH' },
    { title: t('workOrders.priorityLabel.normal'), value: 'NORMAL' },
    { title: t('workOrders.priorityLabel.medium'), value: 'MEDIUM' },
    { title: t('workOrders.priorityLabel.low'), value: 'LOW' },
  ])
}
