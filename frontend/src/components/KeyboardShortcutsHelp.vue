<template>
  <v-dialog v-model="isOpen" max-width="900" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon class="mr-2">mdi-keyboard</v-icon>
        <span class="text-h5">Keyboard Shortcuts</span>
        <v-spacer></v-spacer>
        <v-btn icon variant="text" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <!-- Search shortcuts -->
        <div class="pa-4 border-b">
          <v-text-field
            v-model="searchQuery"
            prepend-inner-icon="mdi-magnify"
            placeholder="Search shortcuts..."
            variant="outlined"
            density="compact"
            hide-details
            clearable
          ></v-text-field>
        </div>

        <!-- Platform indicator -->
        <div class="pa-3 bg-grey-lighten-4 text-center">
          <v-chip size="small" color="primary" variant="tonal">
            <v-icon start>{{ platformIcon }}</v-icon>
            {{ platformName }} Shortcuts
          </v-chip>
        </div>

        <!-- Shortcuts by category -->
        <div class="pa-4">
          <div
            v-for="(shortcuts, category) in filteredShortcuts"
            :key="category"
            class="mb-6"
          >
            <h3 class="text-h6 mb-3 text-primary">
              <v-icon class="mr-2">{{ getCategoryIcon(category) }}</v-icon>
              {{ category }}
            </h3>

            <v-list density="compact" class="bg-transparent">
              <v-list-item
                v-for="shortcut in shortcuts"
                :key="shortcut.id"
                class="px-0 mb-2"
              >
                <template v-slot:prepend>
                  <div class="shortcut-keys mr-4">
                    <kbd
                      v-for="(key, index) in parseShortcutKeys(shortcut.displayKey)"
                      :key="index"
                      class="key-badge"
                    >
                      {{ key }}
                    </kbd>
                  </div>
                </template>

                <v-list-item-title>
                  {{ shortcut.description }}
                </v-list-item-title>

                <template v-slot:append>
                  <v-chip
                    v-if="!shortcut.enabled"
                    size="x-small"
                    color="grey"
                    variant="tonal"
                  >
                    Disabled
                  </v-chip>
                </template>
              </v-list-item>
            </v-list>
          </div>

          <!-- No results -->
          <div v-if="Object.keys(filteredShortcuts).length === 0" class="text-center py-8">
            <v-icon size="64" color="grey-lighten-1">mdi-keyboard-off</v-icon>
            <p class="text-grey mt-4">No shortcuts found matching "{{ searchQuery }}"</p>
          </div>
        </div>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="pa-4">
        <v-spacer></v-spacer>
        <v-btn
          color="primary"
          variant="flat"
          @click="close"
        >
          Close
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue'])

const { getShortcutsByCategory, isMac } = useKeyboardShortcuts({ registerGlobal: false })

const isOpen = ref(props.modelValue)
const searchQuery = ref('')

// Platform info
const platformName = computed(() => isMac.value ? 'macOS' : 'Windows/Linux')
const platformIcon = computed(() => isMac.value ? 'mdi-apple' : 'mdi-microsoft-windows')

// Get all shortcuts
const allShortcuts = computed(() => getShortcutsByCategory())

// Filter shortcuts based on search
const filteredShortcuts = computed(() => {
  if (!searchQuery.value) return allShortcuts.value

  const query = searchQuery.value.toLowerCase()
  const filtered = {}

  Object.entries(allShortcuts.value).forEach(([category, shortcuts]) => {
    const matchingShortcuts = shortcuts.filter(shortcut =>
      shortcut.description.toLowerCase().includes(query) ||
      shortcut.displayKey.toLowerCase().includes(query) ||
      category.toLowerCase().includes(query)
    )

    if (matchingShortcuts.length > 0) {
      filtered[category] = matchingShortcuts
    }
  })

  return filtered
})

/**
 * Get icon for category
 */
const getCategoryIcon = (category) => {
  const icons = {
    'Global': 'mdi-earth',
    'Navigation': 'mdi-navigation',
    'Grid Navigation': 'mdi-table-arrow-right',
    'Grid Editing': 'mdi-table-edit',
    'Grid Clipboard': 'mdi-content-copy',
    'Grid Selection': 'mdi-select-all',
    'Form Actions': 'mdi-form-select',
    'Form Navigation': 'mdi-form-textbox',
    'Form Editing': 'mdi-pencil'
  }
  return icons[category] || 'mdi-keyboard'
}

/**
 * Parse shortcut keys for display
 */
const parseShortcutKeys = (displayKey) => {
  return displayKey.split('+').map(key => key.trim())
}

/**
 * Close dialog
 */
const close = () => {
  isOpen.value = false
}

// Watch for external changes
watch(() => props.modelValue, (newValue) => {
  isOpen.value = newValue
})

// Emit changes
watch(isOpen, (newValue) => {
  emit('update:modelValue', newValue)
})
</script>

<style scoped>
.shortcut-keys {
  display: flex;
  gap: 4px;
  min-width: 180px;
}

.key-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 28px;
  padding: 0 8px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #333;
  background: linear-gradient(180deg, #f8f8f8 0%, #e8e8e8 100%);
  border: 1px solid #ccc;
  border-radius: 4px;
  box-shadow: 0 2px 0 #bbb, 0 3px 2px rgba(0, 0, 0, 0.2);
  text-transform: uppercase;
}

.key-badge:active {
  box-shadow: 0 1px 0 #bbb, 0 1px 1px rgba(0, 0, 0, 0.2);
  transform: translateY(1px);
}

.border-b {
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

/* Dark mode support */
.v-theme--dark .key-badge {
  color: #fff;
  background: linear-gradient(180deg, #4a4a4a 0%, #3a3a3a 100%);
  border-color: #555;
  box-shadow: 0 2px 0 #2a2a2a, 0 3px 2px rgba(0, 0, 0, 0.4);
}

.v-theme--dark .key-badge:active {
  box-shadow: 0 1px 0 #2a2a2a, 0 1px 1px rgba(0, 0, 0, 0.4);
}
</style>
