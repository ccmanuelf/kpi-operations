import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

/**
 * Dual-view (standard ↔ site_adjusted) preference store — Phase 4 dual-view UI.
 *
 * Per-role default per spec § Phase 4 + ratified mapping:
 *   - operator   → site_adjusted (operations-facing; site numbers are the source of truth)
 *   - leader     → site_adjusted (line/quality leads = operations-facing)
 *   - poweruser  → standard      (planners/engineers want the textbook number first)
 *   - admin      → standard      (planners/engineers want the textbook number first)
 *
 * The toggle is always available regardless of role; this only controls the
 * INITIAL value when the user first lands. Once they toggle, their choice is
 * persisted to localStorage and overrides the role default on subsequent loads.
 */

export type DualViewMode = 'standard' | 'site_adjusted'

const STORAGE_KEY = 'kpi-dual-view-mode'

const ROLE_DEFAULTS: Record<string, DualViewMode> = {
  operator: 'site_adjusted',
  leader: 'site_adjusted',
  poweruser: 'standard',
  admin: 'standard',
}

interface StoredPreference {
  mode?: DualViewMode
}

export const useDualViewStore = defineStore('dualView', () => {
  const currentMode = ref<DualViewMode>('standard')
  // True once the user has explicitly toggled — locks out role-default
  // overrides on subsequent role changes (e.g., role re-resolution after
  // a token refresh).
  const userOverridden = ref(false)

  const isStandard = computed(() => currentMode.value === 'standard')
  const isSiteAdjusted = computed(() => currentMode.value === 'site_adjusted')

  const saveToLocalStorage = () => {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ mode: currentMode.value } satisfies StoredPreference)
      )
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to save dual-view preference:', error)
    }
  }

  const loadFromLocalStorage = (): DualViewMode | null => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (!stored) return null
      const data = JSON.parse(stored) as StoredPreference
      return data.mode === 'standard' || data.mode === 'site_adjusted' ? data.mode : null
    } catch {
      return null
    }
  }

  /**
   * Initialise the mode from (a) the user's saved preference if any, otherwise
   * (b) the role default. Call this once on app boot AFTER the user is known.
   */
  const initFromUserRole = (role: string | null | undefined) => {
    const stored = loadFromLocalStorage()
    if (stored !== null) {
      currentMode.value = stored
      userOverridden.value = true
      return
    }
    currentMode.value = (role && ROLE_DEFAULTS[role]) || 'standard'
    userOverridden.value = false
  }

  const setMode = (mode: DualViewMode) => {
    currentMode.value = mode
    userOverridden.value = true
    saveToLocalStorage()
  }

  const toggleMode = () => {
    setMode(currentMode.value === 'standard' ? 'site_adjusted' : 'standard')
  }

  const reset = () => {
    currentMode.value = 'standard'
    userOverridden.value = false
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }

  return {
    currentMode,
    userOverridden,
    isStandard,
    isSiteAdjusted,
    initFromUserRole,
    setMode,
    toggleMode,
    reset,
  }
})
