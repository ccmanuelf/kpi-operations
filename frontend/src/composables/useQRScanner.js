/**
 * QR Scanner Composable
 * Provides QR code scanning and form auto-fill functionality
 */
import { ref, computed } from 'vue'
import api from '@/services/api'

export function useQRScanner() {
  // State
  const isScanning = ref(false)
  const isCameraActive = ref(false)
  const lastScannedData = ref(null)
  const scanError = ref(null)
  const scanHistory = ref([])

  // Camera permissions
  const hasCameraPermission = ref(null)
  const cameraError = ref(null)

  // Computed
  const canScan = computed(() => hasCameraPermission.value === true)

  const lastScanTime = computed(() =>
    lastScannedData.value?.scannedAt
      ? new Date(lastScannedData.value.scannedAt).toLocaleTimeString()
      : null
  )

  // Actions
  const checkCameraPermission = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
      stream.getTracks().forEach(track => track.stop())
      hasCameraPermission.value = true
      cameraError.value = null
      return true
    } catch (error) {
      hasCameraPermission.value = false
      cameraError.value = error.message || 'Camera access denied'
      return false
    }
  }

  const startScanning = async () => {
    if (hasCameraPermission.value === null) {
      await checkCameraPermission()
    }

    if (hasCameraPermission.value) {
      isScanning.value = true
      isCameraActive.value = true
      scanError.value = null
    }
  }

  const stopScanning = () => {
    isScanning.value = false
    isCameraActive.value = false
  }

  const onDecode = async (decodedString) => {
    try {
      scanError.value = null

      // Try to parse as JSON (our QR format)
      let qrData
      try {
        qrData = JSON.parse(decodedString)
      } catch {
        // If not JSON, treat as plain text (work order ID)
        qrData = {
          type: 'work_order',
          id: decodedString,
          version: '1.0'
        }
      }

      // Look up entity from API
      const response = await api.lookupQR(decodedString)

      const result = {
        ...response.data,
        rawData: decodedString,
        scannedAt: new Date().toISOString()
      }

      lastScannedData.value = result

      // Add to history
      addToHistory(result)

      // Stop scanning after successful decode
      stopScanning()

      return result
    } catch (error) {
      scanError.value = error.response?.data?.detail || error.message || 'Failed to look up QR code'
      throw error
    }
  }

  const onDecodeError = (error) => {
    // This is called frequently during scanning, only log actual errors
    if (error && error.message !== 'No QR code found') {
      console.error('QR decode error:', error)
    }
  }

  const addToHistory = (scanResult) => {
    // Remove duplicate if exists
    scanHistory.value = scanHistory.value.filter(
      h => h.entity_type !== scanResult.entity_type ||
           h.entity_data?.id !== scanResult.entity_data?.id
    )

    // Add to front
    scanHistory.value.unshift(scanResult)

    // Keep only last 20
    if (scanHistory.value.length > 20) {
      scanHistory.value = scanHistory.value.slice(0, 20)
    }
  }

  const clearHistory = () => {
    scanHistory.value = []
  }

  const clearLastScan = () => {
    lastScannedData.value = null
    scanError.value = null
  }

  /**
   * Auto-fill form data from QR scan result
   * @param {Object} formData - Reactive form data object
   * @param {Object} scanResult - Result from onDecode
   * @returns {Object} Updated form data
   */
  const autoFillForm = (formData, scanResult) => {
    if (!scanResult?.auto_fill_fields) return formData

    const autoFillFields = scanResult.auto_fill_fields
    const updated = { ...formData }

    Object.keys(autoFillFields).forEach(key => {
      if (key in updated && autoFillFields[key] !== null && autoFillFields[key] !== undefined) {
        updated[key] = autoFillFields[key]
      }
    })

    return updated
  }

  /**
   * Generate QR code for an entity
   * @param {string} entityType - 'work_order', 'product', 'job', 'employee'
   * @param {string|number} entityId - Entity ID
   * @returns {Promise<string>} Base64 image data URL
   */
  const generateQRCode = async (entityType, entityId) => {
    try {
      const response = await api.generateQRImage(entityType, entityId)
      return response.data
    } catch (error) {
      console.error('Failed to generate QR code:', error)
      throw error
    }
  }

  /**
   * Get QR code image URL for an entity
   * @param {string} entityType - 'work_order', 'product', 'job', 'employee'
   * @param {string|number} entityId - Entity ID
   * @returns {string} Image URL
   */
  const getQRImageUrl = (entityType, entityId) => {
    return `/api/qr/${entityType}/${entityId}/image`
  }

  /**
   * Manual lookup by ID
   * @param {string} entityType - 'work_order', 'product', 'job', 'employee'
   * @param {string} entityId - Entity ID
   */
  const manualLookup = async (entityType, entityId) => {
    const qrData = JSON.stringify({
      type: entityType,
      id: entityId,
      version: '1.0'
    })

    return await onDecode(qrData)
  }

  return {
    // State
    isScanning,
    isCameraActive,
    lastScannedData,
    scanError,
    scanHistory,
    hasCameraPermission,
    cameraError,

    // Computed
    canScan,
    lastScanTime,

    // Actions
    checkCameraPermission,
    startScanning,
    stopScanning,
    onDecode,
    onDecodeError,
    clearHistory,
    clearLastScan,
    autoFillForm,
    generateQRCode,
    getQRImageUrl,
    manualLookup
  }
}
