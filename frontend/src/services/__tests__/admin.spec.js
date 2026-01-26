/**
 * Unit tests for Admin API module
 * Tests client, user, threshold, and defect type management
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the client module
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

import api from '../api/client'
import * as adminApi from '../api/admin'

describe('Admin API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Clients CRUD', () => {
    it('getClients calls GET /clients', async () => {
      const mockClients = [{ client_id: 1, name: 'Client A' }]
      api.get.mockResolvedValue({ data: mockClients })

      const result = await adminApi.getClients()

      expect(api.get).toHaveBeenCalledWith('/clients')
      expect(result.data).toEqual(mockClients)
    })

    it('getClient calls GET /clients/:id', async () => {
      const mockClient = { client_id: 1, name: 'Client A' }
      api.get.mockResolvedValue({ data: mockClient })

      const result = await adminApi.getClient(1)

      expect(api.get).toHaveBeenCalledWith('/clients/1')
      expect(result.data).toEqual(mockClient)
    })

    it('createClient calls POST /clients', async () => {
      const clientData = { name: 'New Client', code: 'NC' }
      api.post.mockResolvedValue({ data: { client_id: 2, ...clientData } })

      const result = await adminApi.createClient(clientData)

      expect(api.post).toHaveBeenCalledWith('/clients', clientData)
      expect(result.data.client_id).toBe(2)
    })

    it('updateClient calls PUT /clients/:id', async () => {
      const updateData = { name: 'Updated Client' }
      api.put.mockResolvedValue({ data: { client_id: 1, ...updateData } })

      const result = await adminApi.updateClient(1, updateData)

      expect(api.put).toHaveBeenCalledWith('/clients/1', updateData)
      expect(result.data.name).toBe('Updated Client')
    })

    it('deleteClient calls DELETE /clients/:id', async () => {
      api.delete.mockResolvedValue({})

      await adminApi.deleteClient(1)

      expect(api.delete).toHaveBeenCalledWith('/clients/1')
    })
  })

  describe('Users CRUD', () => {
    it('getUsers calls GET /users', async () => {
      const mockUsers = [{ user_id: 1, username: 'admin' }]
      api.get.mockResolvedValue({ data: mockUsers })

      const result = await adminApi.getUsers()

      expect(api.get).toHaveBeenCalledWith('/users')
      expect(result.data).toEqual(mockUsers)
    })

    it('getUser calls GET /users/:id', async () => {
      const mockUser = { user_id: 1, username: 'admin' }
      api.get.mockResolvedValue({ data: mockUser })

      const result = await adminApi.getUser(1)

      expect(api.get).toHaveBeenCalledWith('/users/1')
      expect(result.data).toEqual(mockUser)
    })

    it('createUser calls POST /users', async () => {
      const userData = { username: 'newuser', email: 'new@example.com', role: 'operator' }
      api.post.mockResolvedValue({ data: { user_id: 2, ...userData } })

      const result = await adminApi.createUser(userData)

      expect(api.post).toHaveBeenCalledWith('/users', userData)
      expect(result.data.user_id).toBe(2)
    })

    it('updateUser calls PUT /users/:id', async () => {
      const updateData = { role: 'supervisor' }
      api.put.mockResolvedValue({ data: { user_id: 1, ...updateData } })

      const result = await adminApi.updateUser(1, updateData)

      expect(api.put).toHaveBeenCalledWith('/users/1', updateData)
      expect(result.data.role).toBe('supervisor')
    })

    it('deleteUser calls DELETE /users/:id', async () => {
      api.delete.mockResolvedValue({})

      await adminApi.deleteUser(1)

      expect(api.delete).toHaveBeenCalledWith('/users/1')
    })
  })

  describe('KPI Thresholds', () => {
    it('getKPIThresholds calls GET /kpi-thresholds', async () => {
      const mockThresholds = [{ kpi_key: 'efficiency', target: 85 }]
      api.get.mockResolvedValue({ data: mockThresholds })

      const result = await adminApi.getKPIThresholds()

      expect(api.get).toHaveBeenCalledWith('/kpi-thresholds', { params: {} })
      expect(result.data).toEqual(mockThresholds)
    })

    it('getKPIThresholds filters by client_id', async () => {
      api.get.mockResolvedValue({ data: [] })

      await adminApi.getKPIThresholds(1)

      expect(api.get).toHaveBeenCalledWith('/kpi-thresholds', { params: { client_id: 1 } })
    })

    it('updateKPIThresholds calls PUT /kpi-thresholds', async () => {
      const thresholdData = { kpi_key: 'efficiency', target: 90, client_id: 1 }
      api.put.mockResolvedValue({ data: thresholdData })

      const result = await adminApi.updateKPIThresholds(thresholdData)

      expect(api.put).toHaveBeenCalledWith('/kpi-thresholds', thresholdData)
      expect(result.data.target).toBe(90)
    })

    it('deleteClientThreshold calls DELETE /kpi-thresholds/:clientId/:kpiKey', async () => {
      api.delete.mockResolvedValue({})

      await adminApi.deleteClientThreshold(1, 'efficiency')

      expect(api.delete).toHaveBeenCalledWith('/kpi-thresholds/1/efficiency')
    })
  })

  describe('Defect Types', () => {
    it('getDefectTypes with clientId calls GET /defect-types/client/:id', async () => {
      const mockDefects = [{ defect_type_id: 1, name: 'Scratch' }]
      api.get.mockResolvedValue({ data: mockDefects })

      const result = await adminApi.getDefectTypes(1)

      expect(api.get).toHaveBeenCalledWith('/defect-types/client/1')
      expect(result.data).toEqual(mockDefects)
    })

    it('getDefectTypes without clientId calls default endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await adminApi.getDefectTypes()

      expect(api.get).toHaveBeenCalledWith('/defect-types/client/default')
    })

    it('getDefectTypes returns empty array on error', async () => {
      api.get.mockRejectedValue(new Error('Not found'))

      const result = await adminApi.getDefectTypes()

      expect(result.data).toEqual([])
    })

    it('getDefectTypesByClient calls with options', async () => {
      api.get.mockResolvedValue({ data: [] })

      await adminApi.getDefectTypesByClient(1, true, false)

      expect(api.get).toHaveBeenCalledWith('/defect-types/client/1', {
        params: { include_inactive: true, include_global: false }
      })
    })

    it('getGlobalDefectTypes calls GET /defect-types/global', async () => {
      api.get.mockResolvedValue({ data: [] })

      await adminApi.getGlobalDefectTypes(true)

      expect(api.get).toHaveBeenCalledWith('/defect-types/global', {
        params: { include_inactive: true }
      })
    })

    it('createDefectType calls POST /defect-types', async () => {
      const defectData = { name: 'Dent', client_id: 1 }
      api.post.mockResolvedValue({ data: { defect_type_id: 1, ...defectData } })

      const result = await adminApi.createDefectType(defectData)

      expect(api.post).toHaveBeenCalledWith('/defect-types', defectData)
      expect(result.data.defect_type_id).toBe(1)
    })

    it('updateDefectType calls PUT /defect-types/:id', async () => {
      const updateData = { name: 'Deep Scratch' }
      api.put.mockResolvedValue({ data: { defect_type_id: 1, ...updateData } })

      const result = await adminApi.updateDefectType(1, updateData)

      expect(api.put).toHaveBeenCalledWith('/defect-types/1', updateData)
      expect(result.data.name).toBe('Deep Scratch')
    })

    it('deleteDefectType calls DELETE /defect-types/:id', async () => {
      api.delete.mockResolvedValue({})

      await adminApi.deleteDefectType(1)

      expect(api.delete).toHaveBeenCalledWith('/defect-types/1')
    })

    it('uploadDefectTypes calls POST with FormData', async () => {
      const file = new File(['test'], 'defects.csv', { type: 'text/csv' })
      api.post.mockResolvedValue({ data: { imported: 5 } })

      const result = await adminApi.uploadDefectTypes(1, file, true)

      expect(api.post).toHaveBeenCalledWith(
        '/defect-types/upload/1',
        expect.any(FormData),
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      expect(result.data.imported).toBe(5)
    })

    it('getDefectTypeTemplate calls GET /defect-types/template/download', async () => {
      api.get.mockResolvedValue({ data: 'template' })

      await adminApi.getDefectTypeTemplate()

      expect(api.get).toHaveBeenCalledWith('/defect-types/template/download')
    })
  })
})
