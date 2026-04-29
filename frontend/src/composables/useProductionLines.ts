/**
 * Composable for production line selection state.
 *
 * Accepts a reactive clientId ref (or a plain value/null) and
 * exposes the lines list, selection, loading state, and a fetch
 * trigger that re-runs whenever clientId changes.
 */
import { ref, watch, type Ref } from 'vue'
import { getProductionLines } from '@/services/api/productionLines'

type ClientIdInput = Ref<string | null | undefined> | string | null | undefined

interface ProductionLine {
  line_id?: string | number
  line_code?: string
  line_name?: string
  [key: string]: unknown
}

export function useProductionLines(clientId: ClientIdInput) {
  const lines = ref<ProductionLine[]>([])
  const selectedLineId = ref<string | number | null>(null)
  const loading = ref(false)
  const error = ref<unknown>(null)

  const fetchLines = async (): Promise<void> => {
    const id =
      clientId && typeof clientId === 'object' && 'value' in clientId
        ? clientId.value
        : (clientId as string | null | undefined)
    if (!id && id !== null) return

    loading.value = true
    error.value = null
    try {
      const { data } = await getProductionLines(id as string)
      lines.value = data
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('Failed to fetch production lines:', err)
      error.value = err
      lines.value = []
    } finally {
      loading.value = false
    }
  }

  if (clientId && typeof clientId === 'object' && 'value' in clientId) {
    watch(clientId, () => {
      selectedLineId.value = null
      fetchLines()
    })
  }

  return { lines, selectedLineId, loading, error, fetchLines }
}
