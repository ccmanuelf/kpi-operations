// Backward compatibility layer
// This file re-exports all API methods from the modular api/ directory
// to maintain compatibility with existing imports like:
//   import api from '@/services/api'

export * from './api/index'
export { default } from './api/index'
