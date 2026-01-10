<template>
  <v-card class="qr-scanner-card" elevation="2">
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-qrcode-scan</v-icon>
      QR Code Scanner
      <v-chip class="ml-2" size="small" color="info" variant="tonal">
        Phase 5
      </v-chip>
    </v-card-title>

    <v-card-text>
      <v-alert type="info" variant="tonal" class="mb-4">
        <template v-slot:prepend>
          <v-icon>mdi-information</v-icon>
        </template>
        <div class="font-weight-medium">Coming in Phase 5</div>
        <div class="text-body-2 mt-1">
          QR Code scanning will enable rapid data entry, work order lookup, and employee time tracking
          directly from production floor devices.
        </div>
      </v-alert>

      <v-row>
        <v-col cols="12" md="6">
          <v-card variant="outlined" class="feature-preview">
            <v-card-item>
              <template v-slot:prepend>
                <v-avatar color="primary" variant="tonal">
                  <v-icon>mdi-briefcase-clock</v-icon>
                </v-avatar>
              </template>
              <v-card-title class="text-subtitle-1">Work Order Lookup</v-card-title>
              <v-card-subtitle>Scan WO QR codes for instant access</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="feature-preview">
            <v-card-item>
              <template v-slot:prepend>
                <v-avatar color="success" variant="tonal">
                  <v-icon>mdi-account-clock</v-icon>
                </v-avatar>
              </template>
              <v-card-title class="text-subtitle-1">Time Tracking</v-card-title>
              <v-card-subtitle>Employee badge scanning for attendance</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="feature-preview">
            <v-card-item>
              <template v-slot:prepend>
                <v-avatar color="warning" variant="tonal">
                  <v-icon>mdi-package-variant</v-icon>
                </v-avatar>
              </template>
              <v-card-title class="text-subtitle-1">Material Tracking</v-card-title>
              <v-card-subtitle>Scan materials for WIP management</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>

        <v-col cols="12" md="6">
          <v-card variant="outlined" class="feature-preview">
            <v-card-item>
              <template v-slot:prepend>
                <v-avatar color="error" variant="tonal">
                  <v-icon>mdi-alert-circle-check</v-icon>
                </v-avatar>
              </template>
              <v-card-title class="text-subtitle-1">Quality Inspection</v-card-title>
              <v-card-subtitle>QR-initiated inspection workflows</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>
      </v-row>

      <!-- Scanner Preview Placeholder -->
      <v-card variant="tonal" color="grey-lighten-4" class="mt-4 scanner-preview">
        <v-card-text class="text-center py-8">
          <v-icon size="64" color="grey-darken-1" class="mb-4">mdi-camera</v-icon>
          <div class="text-h6 text-grey-darken-1">Scanner Preview</div>
          <div class="text-body-2 text-grey">
            Camera access will be enabled in Phase 5
          </div>
          <v-btn
            class="mt-4"
            variant="outlined"
            color="primary"
            prepend-icon="mdi-qrcode"
            disabled
          >
            Start Scanning
          </v-btn>
        </v-card-text>
      </v-card>

      <!-- Demo QR Generation -->
      <v-divider class="my-4" />

      <div class="text-subtitle-2 mb-2">Generate Sample QR Code</div>
      <v-row align="center">
        <v-col cols="12" sm="8">
          <v-text-field
            v-model="sampleData"
            label="Sample Work Order ID"
            variant="outlined"
            density="compact"
            placeholder="WO-2024-001"
            prepend-inner-icon="mdi-file-document"
            hide-details
          />
        </v-col>
        <v-col cols="12" sm="4">
          <v-btn
            color="primary"
            variant="tonal"
            block
            prepend-icon="mdi-qrcode"
            @click="showQRDialog = true"
          >
            Generate QR
          </v-btn>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- QR Code Dialog -->
    <v-dialog v-model="showQRDialog" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-qrcode</v-icon>
          Generated QR Code
        </v-card-title>
        <v-card-text class="text-center">
          <div class="qr-placeholder">
            <v-icon size="120" color="grey-darken-2">mdi-qrcode</v-icon>
          </div>
          <v-chip class="mt-4" color="primary" variant="tonal">
            {{ sampleData || 'WO-2024-001' }}
          </v-chip>
          <div class="text-caption text-grey mt-2">
            QR code generation will be available in Phase 5
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" variant="text" @click="showQRDialog = false">
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref } from 'vue'

const sampleData = ref('WO-2024-001')
const showQRDialog = ref(false)
</script>

<style scoped>
.qr-scanner-card {
  border-radius: 12px;
}

.feature-preview {
  transition: all 0.2s ease;
}

.feature-preview:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.scanner-preview {
  border: 2px dashed #bdbdbd;
  border-radius: 8px;
}

.qr-placeholder {
  background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
  border-radius: 8px;
  padding: 24px;
  display: inline-block;
}
</style>
