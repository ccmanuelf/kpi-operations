/**
 * Composable for KPI dashboard UI actions and snackbar
 * notifications. Snackbar state, navigation, QR scanner events,
 * customizer save callback.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, type RouteLocationRaw } from 'vue-router'

export type SnackbarColor = 'success' | 'error' | 'warning' | 'info'

export interface QRScanData {
  entity_type?: 'work_order' | 'product' | string
  entity_data?: { id?: string | number } & Record<string, unknown>
  [key: string]: unknown
}

export function useKPIDashboardActions() {
  const { t } = useI18n()
  const router = useRouter()

  const snackbar = ref(false)
  const snackbarMessage = ref('')
  const snackbarColor = ref<SnackbarColor>('success')

  const showSnackbar = (message: string, color: SnackbarColor = 'success'): void => {
    snackbarMessage.value = message
    snackbarColor.value = color
    snackbar.value = true
  }

  const showCustomizer = ref(false)
  const showQRScanner = ref(false)

  const navigateToDetail = (route: RouteLocationRaw): void => {
    router.push(route)
  }

  const onCustomizerSaved = (): void => {
    showSnackbar(t('success.dashboardPreferencesSaved'), 'success')
  }

  const handleQRScanned = (data: QRScanData): void => {
    showSnackbar(`Scanned: ${data.entity_type} - ${data.entity_data?.id || 'ID'}`, 'info')
  }

  const handleQRAutoFill = (data: QRScanData): void => {
    showQRScanner.value = false
    showSnackbar(`Auto-filled form data for ${data.entity_type}`, 'success')
    if (data.entity_type === 'work_order') {
      router.push({
        name: 'production-entry',
        query: { work_order_id: String(data.entity_data?.id ?? '') },
      })
    } else if (data.entity_type === 'product') {
      router.push({
        name: 'production-entry',
        query: { product_id: String(data.entity_data?.id ?? '') },
      })
    }
  }

  return {
    snackbar,
    snackbarMessage,
    snackbarColor,
    showSnackbar,
    showCustomizer,
    showQRScanner,
    navigateToDetail,
    onCustomizerSaved,
    handleQRScanned,
    handleQRAutoFill,
  }
}
