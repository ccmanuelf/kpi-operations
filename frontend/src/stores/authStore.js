import { defineStore } from 'pinia'
import api from '@/services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('access_token') || null
  }),

  getters: {
    isAuthenticated: (state) => !!state.token,
    currentUser: (state) => state.user,
    isAdmin: (state) => state.user?.role === 'admin',
    isSupervisor: (state) => ['admin', 'supervisor'].includes(state.user?.role)
  },

  actions: {
    async login(credentials) {
      try {
        const response = await api.login(credentials)
        const { access_token, user } = response.data

        this.token = access_token
        this.user = user

        localStorage.setItem('access_token', access_token)
        localStorage.setItem('user', JSON.stringify(user))

        return { success: true }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Login failed'
        }
      }
    },

    async register(userData) {
      try {
        const response = await api.register(userData)
        return { success: true, user: response.data }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Registration failed'
        }
      }
    },

    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
    }
  }
})
