/**
 * QR scanner composable. Camera permission, scan lifecycle,
 * decode → entity lookup, scan history, form auto-fill.
 */
import { ref, computed } from 'vue'
import api from '@/services/api'

export type EntityType = 'work_order' | 'product' | 'job' | 'employee' | string

export interface QRScanResult {
  entity_type?: EntityType
  entity_data?: { id?: string | number } & Record<string, unknown>
  auto_fill_fields?: Record<string, unknown>
  rawData?: string
  scannedAt?: string
  [key: string]: unknown
}

export function useQRScanner() {
  const isScanning = ref(false)
  const isCameraActive = ref(false)
  const lastScannedData = ref<QRScanResult | null>(null)
  const scanError = ref<string | null>(null)
  const scanHistory = ref<QRScanResult[]>([])

  const hasCameraPermission = ref<boolean | null>(null)
  const cameraError = ref<string | null>(null)

  const canScan = computed(() => hasCameraPermission.value === true)

  const lastScanTime = computed<string | null>(() =>
    lastScannedData.value?.scannedAt
      ? new Date(lastScannedData.value.scannedAt).toLocaleTimeString()
      : null,
  )

  const checkCameraPermission = async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      stream.getTracks().forEach((track) => track.stop())
      hasCameraPermission.value = true
      cameraError.value = null
      return true
    } catch (error) {
      hasCameraPermission.value = false
      cameraError.value =
        error instanceof Error ? error.message : 'Camera access denied'
      return false
    }
  }

  const startScanning = async (): Promise<void> => {
    if (hasCameraPermission.value === null) {
      await checkCameraPermission()
    }

    if (hasCameraPermission.value) {
      isScanning.value = true
      isCameraActive.value = true
      scanError.value = null
    }
  }

  const stopScanning = (): void => {
    isScanning.value = false
    isCameraActive.value = false
  }

  const addToHistory = (scanResult: QRScanResult): void => {
    scanHistory.value = scanHistory.value.filter(
      (h) =>
        h.entity_type !== scanResult.entity_type ||
        h.entity_data?.id !== scanResult.entity_data?.id,
    )

    scanHistory.value.unshift(scanResult)

    if (scanHistory.value.length > 20) {
      scanHistory.value = scanHistory.value.slice(0, 20)
    }
  }

  const onDecode = async (decodedString: string): Promise<QRScanResult> => {
    try {
      scanError.value = null

      // Parse-or-fallback preserved from JS — accept either a JSON
      // payload (our QR format) or a plain work-order id string.
      try {
        JSON.parse(decodedString)
      } catch {
        // Not JSON, but still try the lookup with the raw string;
        // the backend handles plain ids.
      }

      const response = await api.lookupQR(decodedString)

      const result: QRScanResult = {
        ...response.data,
        rawData: decodedString,
        scannedAt: new Date().toISOString(),
      }

      lastScannedData.value = result
      addToHistory(result)
      stopScanning()

      return result
    } catch (error) {
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      scanError.value =
        ax?.response?.data?.detail || ax?.message || 'Failed to look up QR code'
      throw error
    }
  }

  const onDecodeError = (error: Error | null | undefined): void => {
    // Called frequently during scanning; only log actual errors.
    if (error && error.message !== 'No QR code found') {
      // eslint-disable-next-line no-console
      console.error('QR decode error:', error)
    }
  }

  const clearHistory = (): void => {
    scanHistory.value = []
  }

  const clearLastScan = (): void => {
    lastScannedData.value = null
    scanError.value = null
  }

  const autoFillForm = <T extends Record<string, unknown>>(
    formData: T,
    scanResult: QRScanResult | null,
  ): T => {
    if (!scanResult?.auto_fill_fields) return formData

    const autoFillFields = scanResult.auto_fill_fields
    const updated: T = { ...formData }

    Object.keys(autoFillFields).forEach((key) => {
      if (
        key in updated &&
        autoFillFields[key] !== null &&
        autoFillFields[key] !== undefined
      ) {
        ;(updated as Record<string, unknown>)[key] = autoFillFields[key]
      }
    })

    return updated
  }

  const generateQRCode = async (
    entityType: EntityType,
    entityId: string | number,
  ): Promise<unknown> => {
    try {
      const response = await api.generateQRImage(entityType, entityId)
      return response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to generate QR code:', error)
      throw error
    }
  }

  const getQRImageUrl = (entityType: EntityType, entityId: string | number): string =>
    `/api/qr/${entityType}/${entityId}/image`

  const manualLookup = async (
    entityType: EntityType,
    entityId: string,
  ): Promise<QRScanResult> => {
    const qrData = JSON.stringify({
      type: entityType,
      id: entityId,
      version: '1.0',
    })

    return await onDecode(qrData)
  }

  return {
    isScanning,
    isCameraActive,
    lastScannedData,
    scanError,
    scanHistory,
    hasCameraPermission,
    cameraError,
    canScan,
    lastScanTime,
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
    manualLookup,
  }
}
