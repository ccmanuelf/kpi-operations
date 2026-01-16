<template>
  <v-card class="qr-scanner">
    <v-card-title class="d-flex align-center">
      <v-icon class="me-2">mdi-qrcode-scan</v-icon>
      QR Code Scanner
      <v-spacer />
      <v-btn-toggle v-model="mode" mandatory density="compact">
        <v-btn value="scan" size="small">
          <v-icon>mdi-camera</v-icon>
        </v-btn>
        <v-btn value="manual" size="small">
          <v-icon>mdi-keyboard</v-icon>
        </v-btn>
        <v-btn value="generate" size="small">
          <v-icon>mdi-qrcode</v-icon>
        </v-btn>
      </v-btn-toggle>
    </v-card-title>

    <v-card-text>
      <!-- SCAN MODE -->
      <div v-if="mode === 'scan'" class="scanner-area">
        <div v-if="!isScanning" class="text-center pa-8">
          <v-btn color="primary" size="large" @click="startScanning">
            <v-icon start>mdi-camera</v-icon>
            Start Scanning
          </v-btn>
          <p v-if="cameraError" class="text-error mt-2">{{ cameraError }}</p>
        </div>

        <div v-else class="camera-container">
          <qrcode-stream
            @detect="onDetect"
            @camera-on="onCameraOn"
            @camera-off="onCameraOff"
            @error="onCameraError"
            :track="paintOutline"
          >
            <div class="scanner-overlay">
              <div class="scan-region"></div>
            </div>
          </qrcode-stream>
          <v-btn class="stop-btn" color="error" @click="stopScanning">
            Stop
          </v-btn>
        </div>
      </div>

      <!-- MANUAL MODE -->
      <div v-if="mode === 'manual'" class="manual-entry pa-4">
        <v-select v-model="manualType" :items="entityTypes" label="Entity Type" />
        <v-text-field v-model="manualId" label="ID" @keyup.enter="lookupManual" />
        <v-btn color="primary" block @click="lookupManual" :loading="isLoading">
          Look Up
        </v-btn>
      </div>

      <!-- GENERATE MODE -->
      <div v-if="mode === 'generate'" class="generate-area pa-4">
        <v-select v-model="generateType" :items="entityTypes" label="Entity Type" />
        <v-text-field v-model="generateId" label="ID" />
        <v-btn color="primary" block @click="generateQR" :loading="isLoading">
          Generate QR Code
        </v-btn>
        <div v-if="generatedQR" class="text-center mt-4">
          <img :src="generatedQR" alt="QR Code" class="generated-qr" />
          <v-btn class="mt-2" @click="downloadQR">Download</v-btn>
        </div>
      </div>

      <!-- RESULT DISPLAY -->
      <v-alert v-if="scanError" type="error" class="mt-4">{{ scanError }}</v-alert>

      <v-card v-if="lastScannedData" class="mt-4" variant="outlined">
        <v-card-title>Scanned: {{ lastScannedData.entity_type }}</v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item v-for="(value, key) in lastScannedData.auto_fill_fields" :key="key">
              <v-list-item-title>{{ key }}</v-list-item-title>
              <v-list-item-subtitle>{{ value }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-btn color="primary" @click="$emit('auto-fill', lastScannedData)">
            Auto-Fill Form
          </v-btn>
          <v-btn @click="clearLastScan">Clear</v-btn>
        </v-card-actions>
      </v-card>

      <!-- SCAN HISTORY -->
      <v-expansion-panels v-if="scanHistory.length" class="mt-4">
        <v-expansion-panel title="Scan History">
          <v-expansion-panel-text>
            <v-list density="compact">
              <v-list-item v-for="(item, index) in scanHistory" :key="index"
                @click="$emit('auto-fill', item)">
                <v-list-item-title>{{ item.entity_type }}: {{ item.entity_data?.id }}</v-list-item-title>
                <v-list-item-subtitle>{{ formatTime(item.scannedAt) }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'
import { QrcodeStream } from 'vue-qrcode-reader'
import { useQRScanner } from '@/composables/useQRScanner'

const emit = defineEmits(['auto-fill', 'scanned'])

const {
  isScanning,
  lastScannedData,
  scanError,
  scanHistory,
  cameraError,
  startScanning,
  stopScanning,
  onDecode: handleDecode,
  clearLastScan,
  manualLookup,
  generateQRCode
} = useQRScanner()

const mode = ref('scan')
const manualType = ref('work_order')
const manualId = ref('')
const generateType = ref('work_order')
const generateId = ref('')
const generatedQR = ref(null)
const isLoading = ref(false)

const entityTypes = [
  { title: 'Work Order', value: 'work_order' },
  { title: 'Product', value: 'product' },
  { title: 'Job', value: 'job' },
  { title: 'Employee', value: 'employee' }
]

const onCameraOn = () => {
  // Camera is ready
}

const onCameraOff = () => {
  // Camera turned off
}

const onCameraError = (error) => {
  console.error('Camera error:', error)
}

const onDetect = async (detectedCodes) => {
  if (detectedCodes.length === 0) return

  const result = detectedCodes[0].rawValue
  try {
    const data = await handleDecode(result)
    emit('scanned', data)
  } catch (error) {
    console.error('Decode error:', error)
  }
}

const paintOutline = (detectedCodes, ctx) => {
  for (const code of detectedCodes) {
    const [first, ...rest] = code.cornerPoints
    ctx.strokeStyle = '#00FF00'
    ctx.lineWidth = 3
    ctx.beginPath()
    ctx.moveTo(first.x, first.y)
    for (const { x, y } of rest) {
      ctx.lineTo(x, y)
    }
    ctx.lineTo(first.x, first.y)
    ctx.stroke()
  }
}

const lookupManual = async () => {
  if (!manualId.value) return
  isLoading.value = true
  try {
    const data = await manualLookup(manualType.value, manualId.value)
    emit('scanned', data)
  } catch (error) {
    console.error('Manual lookup error:', error)
  } finally {
    isLoading.value = false
  }
}

const generateQR = async () => {
  if (!generateId.value) return
  isLoading.value = true
  try {
    const blob = await generateQRCode(generateType.value, generateId.value)
    generatedQR.value = URL.createObjectURL(blob)
  } catch (error) {
    console.error('Generate error:', error)
  } finally {
    isLoading.value = false
  }
}

const downloadQR = () => {
  if (!generatedQR.value) return
  const a = document.createElement('a')
  a.href = generatedQR.value
  a.download = `qr-${generateType.value}-${generateId.value}.png`
  a.click()
}

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString()
}
</script>

<style scoped>
.camera-container {
  position: relative;
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
}
.scanner-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.scan-region {
  width: 200px;
  height: 200px;
  border: 2px solid #00FF00;
  border-radius: 8px;
}
.stop-btn {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
}
.generated-qr {
  max-width: 200px;
  border: 1px solid #ccc;
  border-radius: 8px;
}
</style>
