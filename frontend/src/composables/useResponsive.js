import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable for responsive breakpoint detection
 *
 * Breakpoints:
 * - Mobile: < 768px
 * - Tablet: 768px - 1024px
 * - Desktop: > 1024px
 *
 * @returns {Object} Reactive breakpoint states and utility functions
 */
export function useResponsive() {
  // Breakpoint constants
  const BREAKPOINTS = {
    MOBILE: 768,
    TABLET: 1024
  }

  // Reactive breakpoint states
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(false)
  const screenWidth = ref(0)
  const screenHeight = ref(0)

  /**
   * Update breakpoint states based on current window size
   */
  const updateBreakpoints = () => {
    const width = window.innerWidth
    const height = window.innerHeight

    screenWidth.value = width
    screenHeight.value = height

    isMobile.value = width < BREAKPOINTS.MOBILE
    isTablet.value = width >= BREAKPOINTS.MOBILE && width < BREAKPOINTS.TABLET
    isDesktop.value = width >= BREAKPOINTS.TABLET
  }

  /**
   * Get current breakpoint name
   * @returns {string} Current breakpoint name
   */
  const getCurrentBreakpoint = () => {
    if (isMobile.value) return 'mobile'
    if (isTablet.value) return 'tablet'
    return 'desktop'
  }

  /**
   * Check if screen is touch device
   * @returns {boolean} True if touch device
   */
  const isTouchDevice = () => {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0
  }

  /**
   * Get optimal grid height based on screen size
   * @returns {string} Grid height
   */
  const getGridHeight = () => {
    if (isMobile.value) return '400px'
    if (isTablet.value) return '500px'
    return '600px'
  }

  /**
   * Get optimal column width based on screen size
   * @param {number} baseWidth - Base column width for desktop
   * @returns {number} Adjusted column width
   */
  const getColumnWidth = (baseWidth = 150) => {
    if (isMobile.value) return Math.max(100, baseWidth * 0.7)
    if (isTablet.value) return Math.max(120, baseWidth * 0.85)
    return baseWidth
  }

  /**
   * Get optimal font size based on screen size
   * @param {number} baseSize - Base font size for desktop
   * @returns {number} Adjusted font size
   */
  const getFontSize = (baseSize = 14) => {
    if (isMobile.value) return Math.max(12, baseSize - 2)
    if (isTablet.value) return Math.max(13, baseSize - 1)
    return baseSize
  }

  /**
   * Get optimal padding based on screen size
   * @param {number} basePadding - Base padding for desktop
   * @returns {number} Adjusted padding
   */
  const getPadding = (basePadding = 16) => {
    if (isMobile.value) return Math.max(8, basePadding * 0.5)
    if (isTablet.value) return Math.max(12, basePadding * 0.75)
    return basePadding
  }

  /**
   * Get optimal row height based on screen size
   * @returns {number} Row height in pixels
   */
  const getRowHeight = () => {
    if (isMobile.value) return 36
    if (isTablet.value) return 40
    return 44
  }

  /**
   * Check if sidebar should be hidden by default
   * @returns {boolean} True if sidebar should be hidden
   */
  const shouldHideSidebar = () => {
    return isMobile.value || isTablet.value
  }

  /**
   * Get optimal button size based on screen size
   * Follows touch-friendly guidelines (44px minimum)
   * @returns {number} Button size in pixels
   */
  const getButtonSize = () => {
    if (isMobile.value) return 44
    if (isTablet.value) return 42
    return 40
  }

  /**
   * Throttle function for performance
   * @param {Function} func - Function to throttle
   * @param {number} delay - Delay in milliseconds
   * @returns {Function} Throttled function
   */
  const throttle = (func, delay = 150) => {
    let timeoutId = null
    let lastRan = null

    return function (...args) {
      const now = Date.now()

      if (!lastRan) {
        func.apply(this, args)
        lastRan = now
      } else {
        clearTimeout(timeoutId)
        timeoutId = setTimeout(() => {
          if (now - lastRan >= delay) {
            func.apply(this, args)
            lastRan = now
          }
        }, delay - (now - lastRan))
      }
    }
  }

  // Throttled resize handler for better performance
  const handleResize = throttle(updateBreakpoints, 150)

  // Lifecycle hooks
  onMounted(() => {
    updateBreakpoints()
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
  })

  return {
    // Breakpoint states
    isMobile,
    isTablet,
    isDesktop,
    screenWidth,
    screenHeight,

    // Utility functions
    getCurrentBreakpoint,
    isTouchDevice,
    getGridHeight,
    getColumnWidth,
    getFontSize,
    getPadding,
    getRowHeight,
    shouldHideSidebar,
    getButtonSize,

    // Manual update
    updateBreakpoints
  }
}
