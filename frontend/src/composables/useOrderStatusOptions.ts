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

/**
 * Options for the Work-Order management status filter.
 *
 * Every member of `WorkOrderStatus` (backend/orm/work_order.py), in lifecycle
 * order. This offered five of the eleven, and the five it offered were the
 * emptiest: RECEIVED, RELEASED, IN_PROGRESS, SHIPPED and CLOSED had no option
 * at all, while ACTIVE — a legacy alias nothing is written as — did. On the
 * seeded demo that left one working choice out of five, and no way to filter
 * for the statuses holding most of the orders.
 *
 * ACTIVE is kept because the column still accepts it and older rows may carry
 * it, but it follows IN_PROGRESS, which is what new work is written as.
 */
export function useWorkOrderStatusOptions() {
  const { t } = useI18n()
  return computed<OrderStatusOption[]>(() => [
    { title: t('workOrders.status.received'), value: 'RECEIVED' },
    { title: t('workOrders.status.released'), value: 'RELEASED' },
    { title: t('workOrders.status.inProgress'), value: 'IN_PROGRESS' },
    { title: t('workOrders.status.active'), value: 'ACTIVE' },
    { title: t('workOrders.status.onHold'), value: 'ON_HOLD' },
    { title: t('workOrders.status.demoted'), value: 'DEMOTED' },
    { title: t('workOrders.status.completed'), value: 'COMPLETED' },
    { title: t('workOrders.status.shipped'), value: 'SHIPPED' },
    { title: t('workOrders.status.closed'), value: 'CLOSED' },
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
