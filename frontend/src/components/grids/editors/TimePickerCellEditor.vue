<template>
  <div class="time-picker-editor" ref="editorRef">
    <v-text-field
      ref="inputRef"
      v-model="localValue"
      type="time"
      variant="outlined"
      density="compact"
      hide-details
      class="time-input"
      @keydown.enter="onEnter"
      @keydown.escape="onEscape"
      @keydown.tab="onTab"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'

const props = defineProps({
  params: {
    type: Object,
    required: true
  }
})

const localValue = ref(props.params.value || '')
const inputRef = ref(null)
const editorRef = ref(null)

// AG Grid cell editor interface
const getValue = () => {
  return localValue.value
}

const isPopup = () => false

const isCancelBeforeStart = () => false

const isCancelAfterEnd = () => false

const focusIn = () => {
  nextTick(() => {
    if (inputRef.value) {
      const input = inputRef.value.$el?.querySelector('input')
      if (input) {
        input.focus()
        input.select()
      }
    }
  })
}

const focusOut = () => {
  // Called when focus leaves the editor
}

const onEnter = () => {
  props.params.stopEditing()
}

const onEscape = () => {
  props.params.stopEditing(true) // Cancel editing
}

const onTab = (event) => {
  props.params.stopEditing()
  // Allow default tab behavior to move to next cell
}

onMounted(() => {
  focusIn()
})

// Expose methods for AG Grid
defineExpose({
  getValue,
  isPopup,
  isCancelBeforeStart,
  isCancelAfterEnd,
  focusIn,
  focusOut
})
</script>

<style scoped>
.time-picker-editor {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  padding: 2px;
}

.time-input {
  width: 100%;
}

.time-input :deep(.v-field__input) {
  padding: 4px 8px;
  min-height: 28px;
}

.time-input :deep(input) {
  font-size: 14px;
}
</style>
