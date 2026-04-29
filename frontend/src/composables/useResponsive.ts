import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Reactive responsive breakpoint detection.
 *   Mobile  : < 768px
 *   Tablet  : 768px – 1023px
 *   Desktop : ≥ 1024px
 */

export type Breakpoint = 'mobile' | 'tablet' | 'desktop'

export function useResponsive() {
  const BREAKPOINTS = {
    MOBILE: 768,
    TABLET: 1024,
  } as const

  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(false)
  const screenWidth = ref(0)
  const screenHeight = ref(0)

  const updateBreakpoints = (): void => {
    const width = window.innerWidth
    const height = window.innerHeight

    screenWidth.value = width
    screenHeight.value = height

    isMobile.value = width < BREAKPOINTS.MOBILE
    isTablet.value = width >= BREAKPOINTS.MOBILE && width < BREAKPOINTS.TABLET
    isDesktop.value = width >= BREAKPOINTS.TABLET
  }

  const getCurrentBreakpoint = (): Breakpoint => {
    if (isMobile.value) return 'mobile'
    if (isTablet.value) return 'tablet'
    return 'desktop'
  }

  const isTouchDevice = (): boolean =>
    'ontouchstart' in window || navigator.maxTouchPoints > 0

  const getGridHeight = (): string => {
    if (isMobile.value) return '400px'
    if (isTablet.value) return '500px'
    return '600px'
  }

  const getColumnWidth = (baseWidth = 150): number => {
    if (isMobile.value) return Math.max(100, baseWidth * 0.7)
    if (isTablet.value) return Math.max(120, baseWidth * 0.85)
    return baseWidth
  }

  const getFontSize = (baseSize = 14): number => {
    if (isMobile.value) return Math.max(12, baseSize - 2)
    if (isTablet.value) return Math.max(13, baseSize - 1)
    return baseSize
  }

  const getPadding = (basePadding = 16): number => {
    if (isMobile.value) return Math.max(8, basePadding * 0.5)
    if (isTablet.value) return Math.max(12, basePadding * 0.75)
    return basePadding
  }

  const getRowHeight = (): number => {
    if (isMobile.value) return 36
    if (isTablet.value) return 40
    return 44
  }

  const shouldHideSidebar = (): boolean => isMobile.value || isTablet.value

  // Touch-friendly button sizes (44px minimum on mobile per Apple HIG / WCAG).
  const getButtonSize = (): number => {
    if (isMobile.value) return 44
    if (isTablet.value) return 42
    return 40
  }

  const throttle = <TArgs extends unknown[]>(
    func: (...args: TArgs) => void,
    delay = 150,
  ): ((...args: TArgs) => void) => {
    let timeoutId: ReturnType<typeof setTimeout> | null = null
    let lastRan: number | null = null

    return function (this: unknown, ...args: TArgs) {
      const now = Date.now()

      if (lastRan === null) {
        func.apply(this, args)
        lastRan = now
      } else {
        if (timeoutId !== null) clearTimeout(timeoutId)
        timeoutId = setTimeout(
          () => {
            if (lastRan !== null && now - lastRan >= delay) {
              func.apply(this, args)
              lastRan = now
            }
          },
          delay - (now - lastRan),
        )
      }
    }
  }

  const handleResize = throttle(updateBreakpoints, 150)

  onMounted(() => {
    updateBreakpoints()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
  })

  return {
    isMobile,
    isTablet,
    isDesktop,
    screenWidth,
    screenHeight,
    getCurrentBreakpoint,
    isTouchDevice,
    getGridHeight,
    getColumnWidth,
    getFontSize,
    getPadding,
    getRowHeight,
    shouldHideSidebar,
    getButtonSize,
    updateBreakpoints,
  }
}
