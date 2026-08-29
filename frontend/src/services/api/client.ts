import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { normalizeStructuredDetail } from './structuredErrors'

const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error),
)

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    // Callers read `data.detail` as a string; the structured 409/422 payloads
    // are objects, so they get flattened into a sentence here rather than at
    // each of the ~40 extraction sites.
    normalizeStructuredDetail(error)
    return Promise.reject(error)
  },
)

export { api }
export default api
