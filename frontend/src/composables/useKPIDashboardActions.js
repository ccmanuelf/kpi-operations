/**
 * Composable for KPI Dashboard UI actions and snackbar notifications.
 * Handles: snackbar state, navigation, QR scanner events, customizer callback.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

export function useKPIDashboardActions() {
  const { t } = useI18n()
  const router = useRouter()

  // --- Snackbar notification ---

  const snackbar = ref(false)
  const snackbarMessage = ref('')
  const snackbarColor = ref('success')

  const showSnackbar = (message, color = 'success') => {
    snackbarMessage.value = message
    snackbarColor.value = color
    snackbar.value = true
  }

  // --- Dialog visibility flags ---

  const showCustomizer = ref(false)
  const showQRScanner = ref(false)

  // --- Navigation ---

  const navigateToDetail = (route) => {
    router.push(route)
  }

  // --- Customizer callback ---

  const onCustomizerSaved = () => {
    showSnackbar(t('success.dashboardPreferencesSaved'), 'success')
  }

  // --- QR Scanner handlers ---

  const handleQRScanned = (data) => {
    showSnackbar(`Scanned: ${data.entity_type} - ${data.entity_data?.id || 'ID'}`, 'info')
  }

  const handleQRAutoFill = (data) => {
    showQRScanner.value = false
    showSnackbar(`Auto-filled form data for ${data.entity_type}`, 'success')
    if (data.entity_type === 'work_order') {
      router.push({ name: 'production-entry', query: { work_order_id: data.entity_data?.id } })
    } else if (data.entity_type === 'product') {
      router.push({ name: 'production-entry', query: { product_id: data.entity_data?.id } })
    }
  }

  return {
    // Snackbar
    snackbar,
    snackbarMessage,
    snackbarColor,
    showSnackbar,
    // Dialog flags
    showCustomizer,
    showQRScanner,
    // Actions
    navigateToDetail,
    onCustomizerSaved,
    handleQRScanned,
    handleQRAutoFill
  }
}
