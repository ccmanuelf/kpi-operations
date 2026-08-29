import { ref, type Ref } from 'vue'

/**
 * Initial-load failure state for the data-entry grids.
 *
 * `productionDataStore`'s fetch actions catch their own errors and resolve with
 * `{success: false}` rather than throwing, and every one of the ten call sites
 * discarded that result. A failed first load therefore left the previous array
 * in place — empty on a cold mount — so the grid rendered "no rows" and the
 * user could not tell a network failure from an empty dataset.
 *
 * A refresh failure is a different thing and deliberately NOT handled here: the
 * grid still holds real rows, so it gets a transient snackbar rather than a
 * banner that would outlive its usefulness.
 */
export interface LoadResult {
  success: boolean
  error?: string
}

export interface GridLoadState {
  /** Backend message from the first failing step; null while the load is good. */
  loadError: Ref<string | null>
  loading: Ref<boolean>
  /** Run steps in order, stopping at the first failure. True if all succeeded. */
  load: (..._steps: Array<() => Promise<LoadResult>>) => Promise<boolean>
  /** Re-run the steps of the most recent load(). */
  retry: () => Promise<boolean>
}

export function useGridLoadState(): GridLoadState {
  const loadError = ref<string | null>(null)
  const loading = ref(false)
  let lastSteps: Array<() => Promise<LoadResult>> = []

  const load = async (...steps: Array<() => Promise<LoadResult>>): Promise<boolean> => {
    lastSteps = steps
    loading.value = true
    loadError.value = null
    try {
      for (const step of steps) {
        // Steps resolve rather than reject, so this is a value check, not a catch.
        const result = await step()
        if (!result?.success) {
          // Empty string would render a banner with no explanation; keep it
          // non-null so the banner still appears, and let the view supply the
          // heading.
          loadError.value = result?.error || ''
          return false
        }
      }
      return true
    } catch (error) {
      // A step that genuinely throws (a caller passing something other than a
      // store action) must not leave the grid silently empty either.
      loadError.value = (error as { message?: string })?.message ?? ''
      return false
    } finally {
      loading.value = false
    }
  }

  const retry = (): Promise<boolean> => load(...lastSteps)

  return { loadError, loading, load, retry }
}

export default useGridLoadState
