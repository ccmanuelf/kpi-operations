# Keyboard Shortcuts Guide

## Overview

The KPI Operations Platform includes a comprehensive keyboard shortcuts system that enables power users to navigate and interact with the application efficiently. The system supports both macOS (⌘) and Windows/Linux (Ctrl) keyboard layouts.

## Quick Access

Press `Ctrl+/` (or `⌘+/` on Mac) to open the keyboard shortcuts help modal at any time.

## Global Shortcuts

These shortcuts work anywhere in the application:

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+S` | Save | Save current form or grid data |
| `Ctrl+N` | New Entry | Create a new entry in the current context |
| `Ctrl+F` | Search | Focus the search field |
| `Ctrl+K` | Command Palette | Open the command palette (coming soon) |
| `Ctrl+/` | Help | Show keyboard shortcuts help |
| `Ctrl+R` | Refresh | Refresh current data |
| `Esc` | Cancel/Close | Close modals or cancel editing |

## Navigation Shortcuts

Navigate between different sections of the application:

| Shortcut | Action | Route |
|----------|--------|-------|
| `Ctrl+D` | Dashboard | Go to main dashboard |
| `Ctrl+P` | Production | Go to production entry |
| `Ctrl+Q` | Quality | Go to quality entry |
| `Ctrl+A` | Attendance | Go to attendance entry |
| `Ctrl+T` | Downtime | Go to downtime entry |

## Grid Shortcuts

These shortcuts work when a data grid (AG Grid) is focused:

### Navigation

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Arrow Keys` | Navigate | Move between cells |
| `Tab` | Next Cell | Move to next editable cell |
| `Shift+Tab` | Previous Cell | Move to previous editable cell |
| `Ctrl+Home` | First Cell | Jump to first cell in grid |
| `Ctrl+End` | Last Cell | Jump to last cell in grid |
| `Page Up` | Scroll Up | Scroll one page up |
| `Page Down` | Scroll Down | Scroll one page down |

### Editing

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Enter` | Edit/Confirm | Start editing cell or confirm edit |
| `Esc` | Cancel | Cancel cell editing |
| `Delete` | Clear | Clear cell content |
| `Backspace` | Clear | Clear cell content |
| `Ctrl+Z` | Undo | Undo last action |
| `Ctrl+Y` | Redo | Redo last undone action |

### Clipboard Operations

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+C` | Copy | Copy selected cells |
| `Ctrl+V` | Paste | Paste clipboard data |
| `Ctrl+X` | Cut | Cut selected cells |

### Selection

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+A` | Select All | Select all rows in grid |
| `Ctrl+Space` | Select Column | Select current column |
| `Shift+Space` | Select Row | Select current row |

## Form Shortcuts

These shortcuts work when a form is focused:

### Actions

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+S` | Save | Save form data |
| `Ctrl+Enter` | Save (Alt) | Alternative save shortcut |
| `Esc` | Cancel | Cancel form editing |
| `Ctrl+Shift+R` | Reset | Reset form to initial values |

### Navigation

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+↓` | Next Field | Move to next form field |
| `Ctrl+↑` | Previous Field | Move to previous form field |
| `Ctrl+Home` | First Field | Focus first form field |
| `Ctrl+End` | Last Field | Focus last form field |
| `Ctrl+E` | First Error | Focus first invalid field |

### Editing

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+Backspace` | Clear Field | Clear current field value |
| `Ctrl+A` | Select All | Select all text in current field |

## Platform-Specific Notes

### macOS
- Replace `Ctrl` with `⌘` (Command key)
- All shortcuts work identically with Command instead of Control

### Windows/Linux
- Use `Ctrl` as shown in the documentation
- Some browser shortcuts may conflict (e.g., `Ctrl+N` for new window)

## Accessibility

The keyboard shortcuts system is designed with accessibility in mind:

- **Screen Reader Support**: All shortcuts are properly announced
- **ARIA Labels**: Interactive elements include keyboard shortcut hints
- **Focus Management**: Clear visual indicators for focused elements
- **No Mouse Required**: Complete application navigation via keyboard

## Customization (Coming Soon)

Future versions will support:
- Custom shortcut mappings
- Import/export shortcut configurations
- Per-user preferences
- Shortcut conflicts detection
- Visual shortcut editor

## Tips for Power Users

1. **Learn Navigation Shortcuts First**: Master `Ctrl+D`, `Ctrl+P`, `Ctrl+Q`, `Ctrl+A`, `Ctrl+T` to quickly move between sections
2. **Use Grid Shortcuts**: Arrow keys and Tab navigation in grids is much faster than mouse clicking
3. **Save Frequently**: `Ctrl+S` works in both grids and forms
4. **Quick Search**: `Ctrl+F` instantly focuses the search field
5. **Help is Always Available**: Press `Ctrl+/` anytime you forget a shortcut

## Implementation Details

For developers integrating keyboard shortcuts:

### Using in Components

```javascript
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'

// Global shortcuts (registered automatically)
const { isHelpModalOpen, toggleHelpModal } = useKeyboardShortcuts()

// Custom shortcuts
const { registerShortcut } = useKeyboardShortcuts({ registerGlobal: false })

registerShortcut('custom-action', {
  key: 'x',
  ctrl: true,
  description: 'My custom action',
  category: 'Custom',
  handler: () => {
    // Your logic here
  }
})
```

### Grid Integration

```javascript
import { useGridShortcuts } from '@/composables/useGridShortcuts'

const gridApi = ref(null)
useGridShortcuts(gridApi)
```

### Form Integration

```javascript
import { useFormShortcuts } from '@/composables/useFormShortcuts'

const formRef = ref(null)
useFormShortcuts(formRef, {
  onSave: handleSave,
  onCancel: handleCancel,
  onReset: handleReset
})
```

## Browser Compatibility

The keyboard shortcuts system works on:
- ✅ Chrome/Edge (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Opera (latest)

## Known Limitations

1. Some browser shortcuts may conflict (e.g., `Ctrl+N` for new window)
2. Shortcuts in input fields are limited to prevent interference with typing
3. Custom shortcut mappings not yet available
4. Some grid operations require AG Grid Enterprise features

## Support

If you encounter issues with keyboard shortcuts:
1. Check that shortcuts are enabled (keyboard icon in top bar should be blue)
2. Ensure you're not in an input field (unless the shortcut explicitly works there)
3. Try refreshing the page
4. Clear browser cache and localStorage

## Changelog

### Version 1.0.0 (Current)
- ✅ Global shortcuts (10+)
- ✅ Navigation shortcuts (5+)
- ✅ Grid shortcuts (18+)
- ✅ Form shortcuts (11+)
- ✅ Help modal
- ✅ Platform detection (Mac/Windows/Linux)
- ✅ Accessibility support
- ✅ Visual indicators

### Planned for Version 1.1.0
- ⏳ Custom shortcut mappings
- ⏳ Command palette
- ⏳ Shortcut conflicts detection
- ⏳ Analytics and usage tracking
- ⏳ Sound effects (optional)
- ⏳ Shortcut hints overlay

---

**Last Updated**: January 2026
**Total Shortcuts**: 44+
