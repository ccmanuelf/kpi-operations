<template>
  <span v-if="showHints" class="keyboard-shortcut-hint">
    <kbd
      v-for="(key, index) in keys"
      :key="index"
      class="key-hint"
    >
      {{ key }}
    </kbd>
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useKeyboardShortcutsStore } from '@/stores/keyboardShortcutsStore'

const props = defineProps({
  shortcut: {
    type: String,
    required: true,
    validator: (value) => {
      // Format: "ctrl+s" or "cmd+shift+n"
      return typeof value === 'string' && value.length > 0
    }
  },
  isMac: {
    type: Boolean,
    default: null // Auto-detect if null
  }
})

const shortcutsStore = useKeyboardShortcutsStore()

const showHints = computed(() => shortcutsStore.preferences.showTooltips)

const platform = computed(() => {
  if (props.isMac !== null) return props.isMac
  return typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0
})

const keys = computed(() => {
  const parts = props.shortcut.toLowerCase().split('+')
  return parts.map(part => {
    switch (part.trim()) {
      case 'ctrl':
      case 'cmd':
      case 'command':
        return platform.value ? '⌘' : 'Ctrl'
      case 'shift':
        return platform.value ? '⇧' : 'Shift'
      case 'alt':
      case 'option':
        return platform.value ? '⌥' : 'Alt'
      case 'enter':
      case 'return':
        return '↵'
      case 'backspace':
        return '⌫'
      case 'delete':
        return '⌦'
      case 'escape':
      case 'esc':
        return 'Esc'
      case 'tab':
        return '⇥'
      case 'space':
        return '␣'
      case 'arrowup':
      case 'up':
        return '↑'
      case 'arrowdown':
      case 'down':
        return '↓'
      case 'arrowleft':
      case 'left':
        return '←'
      case 'arrowright':
      case 'right':
        return '→'
      default:
        return part.toUpperCase()
    }
  })
})
</script>

<style scoped>
.keyboard-shortcut-hint {
  display: inline-flex;
  gap: 2px;
  align-items: center;
  margin-left: 8px;
  opacity: 0.7;
}

.key-hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 4px;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 10px;
  font-weight: 600;
  color: #555;
  background: linear-gradient(180deg, #fafafa 0%, #e8e8e8 100%);
  border: 1px solid #ccc;
  border-radius: 3px;
  box-shadow: 0 1px 0 #bbb, 0 1px 1px rgba(0, 0, 0, 0.1);
  text-transform: uppercase;
}

/* Dark mode */
.v-theme--dark .key-hint {
  color: #ddd;
  background: linear-gradient(180deg, #4a4a4a 0%, #3a3a3a 100%);
  border-color: #555;
  box-shadow: 0 1px 0 #2a2a2a, 0 1px 1px rgba(0, 0, 0, 0.3);
}
</style>
