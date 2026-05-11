/**
 * Unit tests for Composables
 * Tests: useResponsive, useKeyboardShortcuts, useUnsavedChanges, useQRScanner
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { withSetup as inComponent } from '../../test/composable-test-utils'

// ---------- Mock setup for vue-router (useUnsavedChanges needs it) ----------
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn()
  }),
  onBeforeRouteLeave: vi.fn()
}))

// ---------- Mock @/services/api (useQRScanner needs it) ----------
const mockLookupQR = vi.fn()
const mockGenerateQRImage = vi.fn()
vi.mock('@/services/api', () => ({
  default: {
    lookupQR: (...args) => mockLookupQR(...args),
    generateQRImage: (...args) => mockGenerateQRImage(...args)
  }
}))

// ============================================================
// useResponsive
// ============================================================
describe('useResponsive', () => {
  let useResponsive

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useResponsive.js')
    useResponsive = mod.useResponsive
  })

  // useResponsive calls onMounted/onUnmounted to attach a window resize
  // listener; the wrapper component gives those hooks an active instance.
  const mount = () => inComponent(() => useResponsive())

  const setWindow = (w, h) => {
    Object.defineProperty(window, 'innerWidth', { value: w, writable: true, configurable: true })
    Object.defineProperty(window, 'innerHeight', { value: h, writable: true, configurable: true })
  }

  it('detects mobile breakpoint when width < 768', () => {
    setWindow(400, 800)
    const h = mount()
    h.updateBreakpoints()
    expect(h.isMobile.value).toBe(true)
    expect(h.isTablet.value).toBe(false)
    expect(h.isDesktop.value).toBe(false)
  })

  it('detects tablet breakpoint when 768 <= width < 1024', () => {
    setWindow(800, 600)
    const h = mount()
    h.updateBreakpoints()
    expect(h.isMobile.value).toBe(false)
    expect(h.isTablet.value).toBe(true)
    expect(h.isDesktop.value).toBe(false) // 800 < 1024 (TABLET threshold)
  })

  it('detects desktop breakpoint when width >= 1024', () => {
    setWindow(1200, 800)
    const h = mount()
    h.updateBreakpoints()
    expect(h.isMobile.value).toBe(false)
    expect(h.isTablet.value).toBe(false)
    expect(h.isDesktop.value).toBe(true)
  })

  it('returns correct breakpoint name via getCurrentBreakpoint', () => {
    setWindow(400, 800)
    const h = mount()
    h.updateBreakpoints()
    expect(h.getCurrentBreakpoint()).toBe('mobile')
  })

  it('returns responsive grid height based on breakpoint', () => {
    setWindow(400, 800)
    const h = mount()
    h.updateBreakpoints()
    expect(h.getGridHeight()).toBe('400px')
  })

  it('adjusts column width for mobile', () => {
    setWindow(400, 800)
    const h = mount()
    h.updateBreakpoints()
    // 150 * 0.7 = 105
    expect(h.getColumnWidth(150)).toBe(105)
  })

  it('returns desktop column width when on desktop', () => {
    setWindow(1200, 800)
    const h = mount()
    h.updateBreakpoints()
    expect(h.getColumnWidth(150)).toBe(150)
  })

  it('shouldHideSidebar returns true on mobile/tablet', () => {
    setWindow(400, 800)
    const h = mount()
    h.updateBreakpoints()
    expect(h.shouldHideSidebar()).toBe(true)
  })

  it('tracks screen dimensions', () => {
    setWindow(1024, 768)
    const h = mount()
    h.updateBreakpoints()
    expect(h.screenWidth.value).toBe(1024)
    expect(h.screenHeight.value).toBe(768)
  })
})

// ============================================================
// useKeyboardShortcuts
// ============================================================
describe('useKeyboardShortcuts', () => {
  // Wraps the composable in a real component so onMounted fires.
  // Tests don't use the return value (registerShortcut is the side
  // effect under test), so the shared inComponent helper suits.
  const createShortcutWrapper = (setupFn) => inComponent(setupFn)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('registers and triggers a shortcut', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler)
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 's',
      ctrlKey: true,
      bubbles: true
    })
    window.dispatchEvent(event)

    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('does not trigger shortcut for non-matching keys', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler)
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 'a',
      ctrlKey: true,
      bubbles: true
    })
    window.dispatchEvent(event)

    expect(handler).not.toHaveBeenCalled()
  })

  it('unregisters a shortcut', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut, unregisterShortcut } = useKeyboardShortcuts()
      registerShortcut('escape', handler)
      unregisterShortcut('escape')
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 'escape',
      bubbles: true
    })
    window.dispatchEvent(event)

    expect(handler).not.toHaveBeenCalled()
  })

  it('clears all shortcuts', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler1 = vi.fn()
    const handler2 = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut, clearShortcuts } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler1)
      registerShortcut('escape', handler2)
      clearShortcuts()
      return {}
    })

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'escape', bubbles: true }))

    expect(handler1).not.toHaveBeenCalled()
    expect(handler2).not.toHaveBeenCalled()
  })

  it('prevents default when preventDefault option is true (default)', async () => {
    const { useKeyboardShortcuts } = await import('../useKeyboardShortcuts.ts')
    const handler = vi.fn()

    createShortcutWrapper(() => {
      const { registerShortcut } = useKeyboardShortcuts()
      registerShortcut('ctrl+s', handler)
      return {}
    })

    const event = new KeyboardEvent('keydown', {
      key: 's',
      ctrlKey: true,
      bubbles: true,
      cancelable: true
    })
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault')
    window.dispatchEvent(event)

    expect(preventDefaultSpy).toHaveBeenCalled()
  })
})

// ============================================================
// useUnsavedChanges
// ============================================================
describe('useUnsavedChanges', () => {
  let useUnsavedChanges

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useUnsavedChanges.ts')
    useUnsavedChanges = mod.useUnsavedChanges
  })

  // useUnsavedChanges calls onMounted / onUnmounted / onBeforeRouteLeave,
  // all of which require an active Vue component instance via setup().
  // Wrap in a test component (shared `inComponent` helper) so Vue's
  // lifecycle injection has a valid scope.
  const useInsideComponent = (options) => inComponent(() => useUnsavedChanges(options))

  it('initializes with no unsaved changes', () => {
    const h = useInsideComponent()
    expect(h.hasUnsavedChanges.value).toBe(false)
  })

  it('marks form as dirty', () => {
    const h = useInsideComponent()
    h.markDirty()
    expect(h.hasUnsavedChanges.value).toBe(true)
  })

  it('marks form as clean after save', () => {
    const h = useInsideComponent()
    h.markDirty()
    expect(h.hasUnsavedChanges.value).toBe(true)
    h.markClean()
    expect(h.hasUnsavedChanges.value).toBe(false)
  })

  it('confirmNavigation returns true when no unsaved changes', () => {
    const h = useInsideComponent()
    expect(h.confirmNavigation()).toBe(true)
  })

  it('confirmNavigation prompts user when there are unsaved changes', () => {
    window.confirm = vi.fn(() => false)
    const h = useInsideComponent()
    h.markDirty()

    const result = h.confirmNavigation()

    expect(window.confirm).toHaveBeenCalled()
    expect(result).toBe(false)
  })

  it('setEnabled toggles the warning functionality', () => {
    const h = useInsideComponent()
    expect(h.isEnabled.value).toBe(true)
    h.setEnabled(false)
    expect(h.isEnabled.value).toBe(false)
  })

  it('confirmNavigation returns true when disabled even with unsaved changes', () => {
    const h = useInsideComponent()
    h.markDirty()
    h.setEnabled(false)
    expect(h.confirmNavigation()).toBe(true)
  })

  it('accepts custom message option', () => {
    window.confirm = vi.fn(() => true)
    const customMsg = 'Custom warning message'
    const h = useInsideComponent({ message: customMsg })
    h.markDirty()
    h.confirmNavigation()
    expect(window.confirm).toHaveBeenCalledWith(customMsg)
  })
})

// ============================================================
// useQRScanner
// ============================================================
describe('useQRScanner', () => {
  let useQRScanner

  beforeEach(async () => {
    vi.clearAllMocks()
    const mod = await import('../useQRScanner.js')
    useQRScanner = mod.useQRScanner
  })

  it('initializes with scanning inactive', () => {
    const { isScanning, isCameraActive, lastScannedData, scanError } = useQRScanner()

    expect(isScanning.value).toBe(false)
    expect(isCameraActive.value).toBe(false)
    expect(lastScannedData.value).toBeNull()
    expect(scanError.value).toBeNull()
  })

  it('stopScanning sets flags to false', () => {
    const { isScanning, isCameraActive, stopScanning } = useQRScanner()
    isScanning.value = true
    isCameraActive.value = true

    stopScanning()

    expect(isScanning.value).toBe(false)
    expect(isCameraActive.value).toBe(false)
  })

  it('clearHistory empties scan history', () => {
    const { scanHistory, clearHistory } = useQRScanner()
    scanHistory.value = [{ entity_type: 'work_order', entity_data: { id: 1 } }]

    clearHistory()

    expect(scanHistory.value).toEqual([])
  })

  it('clearLastScan resets last scan data and error', () => {
    const { lastScannedData, scanError, clearLastScan } = useQRScanner()
    lastScannedData.value = { foo: 'bar' }
    scanError.value = 'some error'

    clearLastScan()

    expect(lastScannedData.value).toBeNull()
    expect(scanError.value).toBeNull()
  })

  it('autoFillForm fills matching fields from scan result', () => {
    const { autoFillForm } = useQRScanner()
    const formData = { work_order_id: '', product_id: '', notes: '' }
    const scanResult = {
      auto_fill_fields: {
        work_order_id: 'WO-123',
        product_id: 42,
        unknown_field: 'ignored'
      }
    }

    const updated = autoFillForm(formData, scanResult)

    expect(updated.work_order_id).toBe('WO-123')
    expect(updated.product_id).toBe(42)
    expect(updated.notes).toBe('')
  })

  it('autoFillForm returns original data when no auto_fill_fields', () => {
    const { autoFillForm } = useQRScanner()
    const formData = { work_order_id: 'test' }
    const scanResult = {}

    const updated = autoFillForm(formData, scanResult)

    expect(updated.work_order_id).toBe('test')
  })

  it('getQRImageUrl returns correct URL', () => {
    const { getQRImageUrl } = useQRScanner()
    const url = getQRImageUrl('work_order', 123)
    expect(url).toBe('/api/qr/work_order/123/image')
  })

  it('canScan computed is true when permission granted', () => {
    const { hasCameraPermission, canScan } = useQRScanner()
    hasCameraPermission.value = true
    expect(canScan.value).toBe(true)
  })

  it('canScan computed is false when permission denied', () => {
    const { hasCameraPermission, canScan } = useQRScanner()
    hasCameraPermission.value = false
    expect(canScan.value).toBe(false)
  })
})
