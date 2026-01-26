import api from './client'

export const login = (credentials) => api.post('/auth/login', credentials)

export const register = (userData) => api.post('/auth/register', userData)

export const getCurrentUser = () => api.get('/auth/me')

export const forgotPassword = (email) => api.post('/auth/forgot-password', { email })

export const resetPassword = (token, newPassword) => api.post('/auth/reset-password', { token, new_password: newPassword })

export const verifyResetToken = (token) => api.get(`/auth/verify-reset-token/${token}`)

export const changePassword = (currentPassword, newPassword) => api.post('/auth/change-password', {
  current_password: currentPassword,
  new_password: newPassword
})

export const refreshToken = () => api.post('/auth/refresh')

export const verifyEmail = (token) => api.post('/auth/verify-email', { token })
