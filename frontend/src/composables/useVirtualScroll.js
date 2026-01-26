/**
 * Virtual Scrolling Composable
 *
 * Provides efficient rendering for large lists by only rendering
 * visible items. Critical for performance on mobile devices and
 * large data tables in manufacturing KPI dashboards.
 *
 * @example
 * const {
 *   visibleItems,
 *   containerProps,
 *   wrapperProps,
 *   scrollToIndex
 * } = useVirtualScroll(items, {
 *   itemHeight: 50,
 *   overscan: 5
 * })
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { throttle } from '@/utils/performance'

/**
 * Virtual scroll composable for efficient list rendering
 *
 * @param {Ref<Array>} items - Reactive array of items to render
 * @param {Object} options - Configuration options
 * @param {number} options.itemHeight - Height of each item in pixels
 * @param {number} options.overscan - Number of items to render above/below viewport
 * @param {number} options.containerHeight - Fixed container height (optional)
 * @returns {Object} Virtual scroll state and handlers
 */
export function useVirtualScroll(items, options = {}) {
  const {
    itemHeight = 50,
    overscan = 5,
    containerHeight = null
  } = options

  // State
  const scrollTop = ref(0)
  const viewportHeight = ref(containerHeight || 400)
  const containerRef = ref(null)

  // Computed values for virtual rendering
  const totalHeight = computed(() => items.value.length * itemHeight)

  const startIndex = computed(() => {
    const start = Math.floor(scrollTop.value / itemHeight) - overscan
    return Math.max(0, start)
  })

  const endIndex = computed(() => {
    const visibleCount = Math.ceil(viewportHeight.value / itemHeight)
    const end = Math.floor(scrollTop.value / itemHeight) + visibleCount + overscan
    return Math.min(items.value.length, end)
  })

  const visibleItems = computed(() => {
    return items.value.slice(startIndex.value, endIndex.value).map((item, index) => ({
      item,
      index: startIndex.value + index,
      style: {
        position: 'absolute',
        top: `${(startIndex.value + index) * itemHeight}px`,
        height: `${itemHeight}px`,
        width: '100%'
      }
    }))
  })

  const offsetY = computed(() => startIndex.value * itemHeight)

  // Throttled scroll handler for performance
  const handleScroll = throttle((event) => {
    if (event.target) {
      scrollTop.value = event.target.scrollTop
    }
  }, 16) // ~60fps

  // Resize observer for dynamic container height
  let resizeObserver = null

  function setupResizeObserver() {
    if (!containerRef.value || containerHeight) return

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          viewportHeight.value = entry.contentRect.height
        }
      })
      resizeObserver.observe(containerRef.value)
    }
  }

  function cleanupResizeObserver() {
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
  }

  // Scroll to specific index
  function scrollToIndex(index, behavior = 'smooth') {
    if (containerRef.value) {
      const targetTop = index * itemHeight
      containerRef.value.scrollTo({
        top: targetTop,
        behavior
      })
    }
  }

  // Scroll to top
  function scrollToTop(behavior = 'smooth') {
    scrollToIndex(0, behavior)
  }

  // Scroll to bottom
  function scrollToBottom(behavior = 'smooth') {
    scrollToIndex(items.value.length - 1, behavior)
  }

  // Props for the container element
  const containerProps = computed(() => ({
    ref: (el) => {
      containerRef.value = el
      if (el) setupResizeObserver()
    },
    style: {
      height: containerHeight ? `${containerHeight}px` : '100%',
      overflow: 'auto',
      position: 'relative'
    },
    onScroll: handleScroll
  }))

  // Props for the wrapper element (creates scroll height)
  const wrapperProps = computed(() => ({
    style: {
      height: `${totalHeight.value}px`,
      position: 'relative'
    }
  }))

  // Lifecycle
  onMounted(() => {
    if (containerRef.value) {
      setupResizeObserver()
    }
  })

  onUnmounted(() => {
    cleanupResizeObserver()
    handleScroll.cancel()
  })

  // Reset scroll position when items change significantly
  watch(() => items.value.length, (newLen, oldLen) => {
    if (Math.abs(newLen - oldLen) > 100) {
      scrollTop.value = 0
    }
  })

  return {
    // State
    visibleItems,
    scrollTop,
    viewportHeight,
    totalHeight,
    startIndex,
    endIndex,

    // Refs
    containerRef,

    // Props helpers
    containerProps,
    wrapperProps,

    // Methods
    scrollToIndex,
    scrollToTop,
    scrollToBottom
  }
}

/**
 * Virtual scroll composable with variable item heights
 *
 * @param {Ref<Array>} items - Reactive array of items
 * @param {Object} options - Configuration options
 * @param {Function} options.estimatedHeight - Function to estimate item height
 * @param {number} options.overscan - Number of items to render above/below
 * @returns {Object} Virtual scroll state and handlers
 */
export function useVariableVirtualScroll(items, options = {}) {
  const {
    estimatedHeight = () => 50,
    overscan = 3
  } = options

  // Cache measured heights
  const heightCache = ref(new Map())
  const scrollTop = ref(0)
  const viewportHeight = ref(400)
  const containerRef = ref(null)

  // Get height for an item (cached or estimated)
  function getItemHeight(index) {
    if (heightCache.value.has(index)) {
      return heightCache.value.get(index)
    }
    return estimatedHeight(items.value[index], index)
  }

  // Calculate positions for all items
  const itemPositions = computed(() => {
    const positions = []
    let currentTop = 0

    for (let i = 0; i < items.value.length; i++) {
      const height = getItemHeight(i)
      positions.push({
        index: i,
        top: currentTop,
        height,
        bottom: currentTop + height
      })
      currentTop += height
    }

    return positions
  })

  const totalHeight = computed(() => {
    if (itemPositions.value.length === 0) return 0
    const lastItem = itemPositions.value[itemPositions.value.length - 1]
    return lastItem.bottom
  })

  // Find visible range using binary search
  const visibleRange = computed(() => {
    const positions = itemPositions.value
    if (positions.length === 0) return { start: 0, end: 0 }

    const viewTop = scrollTop.value
    const viewBottom = scrollTop.value + viewportHeight.value

    // Binary search for start index
    let start = 0
    let end = positions.length - 1

    while (start < end) {
      const mid = Math.floor((start + end) / 2)
      if (positions[mid].bottom < viewTop) {
        start = mid + 1
      } else {
        end = mid
      }
    }

    const startIndex = Math.max(0, start - overscan)

    // Find end index
    end = positions.length - 1
    while (start < end) {
      const mid = Math.ceil((start + end) / 2)
      if (positions[mid].top > viewBottom) {
        end = mid - 1
      } else {
        start = mid
      }
    }

    const endIndex = Math.min(positions.length, end + overscan + 1)

    return { start: startIndex, end: endIndex }
  })

  const visibleItems = computed(() => {
    const { start, end } = visibleRange.value
    const positions = itemPositions.value

    return positions.slice(start, end).map(pos => ({
      item: items.value[pos.index],
      index: pos.index,
      style: {
        position: 'absolute',
        top: `${pos.top}px`,
        minHeight: `${pos.height}px`,
        width: '100%'
      }
    }))
  })

  // Update height after render
  function updateItemHeight(index, height) {
    if (height !== heightCache.value.get(index)) {
      heightCache.value.set(index, height)
    }
  }

  const handleScroll = throttle((event) => {
    scrollTop.value = event.target.scrollTop
  }, 16)

  const containerProps = computed(() => ({
    ref: (el) => { containerRef.value = el },
    style: {
      height: '100%',
      overflow: 'auto',
      position: 'relative'
    },
    onScroll: handleScroll
  }))

  const wrapperProps = computed(() => ({
    style: {
      height: `${totalHeight.value}px`,
      position: 'relative'
    }
  }))

  onUnmounted(() => {
    handleScroll.cancel()
  })

  return {
    visibleItems,
    scrollTop,
    totalHeight,
    containerRef,
    containerProps,
    wrapperProps,
    updateItemHeight
  }
}

/**
 * Hook for measuring rendered item height
 * Use with v-virtual-scroll-item directive
 *
 * @param {Function} onMeasure - Callback with measured height
 * @returns {Object} Ref to attach to item element
 */
export function useItemMeasure(onMeasure) {
  const itemRef = ref(null)

  onMounted(() => {
    if (itemRef.value && onMeasure) {
      const rect = itemRef.value.getBoundingClientRect()
      onMeasure(rect.height)
    }
  })

  return itemRef
}

export default useVirtualScroll
