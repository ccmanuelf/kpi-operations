import api from './client'

type ExportParams = Record<string, unknown>

const blobGet = (url: string, params: ExportParams) =>
  api.get(url, { params, responseType: 'blob' })

export function exportProductionEntries(params: ExportParams = {}) {
  return blobGet('/export/production-entries', params)
}

export function exportWorkOrders(params: ExportParams = {}) {
  return blobGet('/export/work-orders', params)
}

export function exportQualityInspections(params: ExportParams = {}) {
  return blobGet('/export/quality-inspections', params)
}

export function exportDowntimeEvents(params: ExportParams = {}) {
  return blobGet('/export/downtime-events', params)
}

export function exportAttendance(params: ExportParams = {}) {
  return blobGet('/export/attendance', params)
}

export function exportEmployees(params: ExportParams = {}) {
  return blobGet('/export/employees', params)
}

export function exportProducts(params: ExportParams = {}) {
  return blobGet('/export/products', params)
}

export function exportShifts(params: ExportParams = {}) {
  return blobGet('/export/shifts', params)
}

export function exportHolds(params: ExportParams = {}) {
  return blobGet('/export/holds', params)
}
