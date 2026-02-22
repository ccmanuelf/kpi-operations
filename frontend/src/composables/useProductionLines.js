/**
 * Composable for production line selection state.
 *
 * Provides reactive state for fetching and selecting production lines.
 * Accepts a reactive clientId ref and exposes lines list, selected line,
 * loading state, and a fetch method.
 */
import { ref, watch } from 'vue'
import { getProductionLines } from '@/services/api/productionLines'

export function useProductionLines(clientId) {
  const lines = ref([])
  const selectedLineId = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const fetchLines = async () => {
    const id = clientId?.value ?? clientId
    if (!id && id !== null) return

    loading.value = true
    error.value = null
    try {
      const { data } = await getProductionLines(id)
      lines.value = data
    } catch (err) {
      console.error('Failed to fetch production lines:', err)
      error.value = err
      lines.value = []
    } finally {
      loading.value = false
    }
  }

  // Re-fetch when clientId changes (if it is a ref)
  if (clientId && typeof clientId === 'object' && 'value' in clientId) {
    watch(clientId, () => {
      selectedLineId.value = null
      fetchLines()
    })
  }

  return { lines, selectedLineId, loading, error, fetchLines }
}
