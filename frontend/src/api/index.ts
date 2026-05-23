import axios from 'axios'
import type {
  ApiResponse, PaginatedResponse,
  CoalYard, CoalYardDetail, YardStatus,
  StockIn, StockInDetail, StockOut, StockOutStatus, Stocktake, StocktakeStatus,
  OverviewData, YardUtilization, CoalTypeInventory,
  InOutTrendItem, AgingAlertItem, InventoryHistoryItem,
  TemperatureReading, TempTrendItem, TemperatureSource,
  BlendingAdviceItem,
} from '../types'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err.response?.data || err)
  },
)

function buildUrl(path: string, params?: Record<string, string | number | undefined>) {
  const qs = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') qs.append(k, String(v))
    }
  }
  return `/api${path}${qs.toString() ? `?${qs.toString()}` : ''}`
}

async function downloadFile(url: string, fallbackName = 'export.csv') {
  const token = localStorage.getItem('token')
  const resp = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!resp.ok) throw new Error(`下载失败 ${resp.status}`)
  const blob = await resp.blob()
  const cd = resp.headers.get('Content-Disposition') || ''
  let filename = fallbackName
  const m = cd.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
  if (m) {
    try { filename = decodeURIComponent(m[1].replace(/"/g, '')) } catch { /* ignore */ }
  }
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

export const authApi = {
  login: (username: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return api.post<unknown, { access_token: string; token_type: string }>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },
  me: () => api.get<unknown, ApiResponse<{ id: number; username: string; role: string }>>('/auth/me'),
}

export const yardApi = {
  list: (params?: { page?: number; page_size?: number; status?: YardStatus; coal_type?: string; keyword?: string }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<CoalYard>>>('/yards', { params }),
  create: (data: Partial<CoalYard>) =>
    api.post<unknown, ApiResponse<CoalYard>>('/yards', data),
  get: (id: number) =>
    api.get<unknown, ApiResponse<CoalYardDetail>>(`/yards/${id}`),
  update: (id: number, data: Partial<CoalYard>) =>
    api.put<unknown, ApiResponse<CoalYard>>(`/yards/${id}`, data),
  maintenance: (id: number) => api.post<unknown, ApiResponse<null>>(`/yards/${id}/maintenance`),
  activate: (id: number) => api.post<unknown, ApiResponse<null>>(`/yards/${id}/activate`),
  disable: (id: number) => api.post<unknown, ApiResponse<null>>(`/yards/${id}/disable`),
  exportCsv: (params?: { status?: YardStatus; coal_type?: string; keyword?: string }) =>
    downloadFile(buildUrl('/yards/export', params), '煤场堆区列表.csv'),
}

export const stockInApi = {
  list: (params?: { page?: number; page_size?: number; yard_id?: number; coal_type?: string; order_no?: string; has_remaining?: boolean }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<StockIn>>>('/stock-in', { params }),
  create: (data: Partial<StockIn>) =>
    api.post<unknown, ApiResponse<StockIn>>('/stock-in', data),
  get: (id: number) => api.get<unknown, ApiResponse<StockInDetail>>(`/stock-in/${id}`),
  update: (id: number, data: Partial<StockIn>) =>
    api.put<unknown, ApiResponse<StockIn>>(`/stock-in/${id}`, data),
  syncQuality: (id: number) => api.post<unknown, ApiResponse<StockIn>>(`/stock-in/${id}/sync-quality`),
  exportCsv: (params?: { yard_id?: number; coal_type?: string }) =>
    downloadFile(buildUrl('/stock-in/export', params), '入场记录.csv'),
}

export const stockOutApi = {
  list: (params?: { page?: number; page_size?: number; yard_id?: number; coal_type?: string; destination?: string; status?: StockOutStatus }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<StockOut>>>('/stock-out', { params }),
  create: (data: Partial<StockOut>) =>
    api.post<unknown, ApiResponse<StockOut>>('/stock-out', data),
  get: (id: number) => api.get<unknown, ApiResponse<StockOut>>(`/stock-out/${id}`),
  approve: (id: number, approved: boolean, approval_notes?: string) =>
    api.post<unknown, ApiResponse<StockOut>>(`/stock-out/${id}/approve`, { approved, approval_notes }),
  exportCsv: (params?: { yard_id?: number; coal_type?: string }) =>
    downloadFile(buildUrl('/stock-out/export', params), '出场记录.csv'),
}

export const stocktakeApi = {
  list: (params?: { page?: number; page_size?: number; yard_id?: number; status?: StocktakeStatus }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<Stocktake>>>('/stocktake', { params }),
  create: (data: { yard_id: number; actual_inventory: number; measured_at: string; method?: string; reason?: string }) =>
    api.post<unknown, ApiResponse<Stocktake>>('/stocktake', data),
  get: (id: number) => api.get<unknown, ApiResponse<Stocktake>>(`/stocktake/${id}`),
  approve: (id: number, approved: boolean, approval_notes?: string) =>
    api.post<unknown, ApiResponse<Stocktake>>(`/stocktake/${id}/approve`, { approved, approval_notes }),
  bookInventory: (yard_id: number) =>
    api.get<unknown, ApiResponse<{ yard_id: number; yard_code: string; yard_name: string; book_inventory: number }>>(`/stocktake/yard/${yard_id}/book-inventory`),
}

export const temperatureApi = {
  list: (params?: { page?: number; page_size?: number; yard_id?: number; min_temp?: number }) =>
    api.get<unknown, ApiResponse<PaginatedResponse<TemperatureReading>>>('/temperature', { params }),
  create: (data: { yard_id: number; spot: string; temperature: number; source?: TemperatureSource; measured_at: string; notes?: string }) =>
    api.post<unknown, ApiResponse<TemperatureReading>>('/temperature', data),
  remove: (id: number) => api.delete<unknown, ApiResponse<null>>(`/temperature/${id}`),
  hotspots: (limit = 10) =>
    api.get<unknown, ApiResponse<TemperatureReading[]>>('/temperature/hotspots', { params: { limit } }),
  trend: (yard_id: number, days = 7) =>
    api.get<unknown, ApiResponse<TempTrendItem[]>>(`/temperature/yard/${yard_id}/trend`, { params: { days } }),
}

export const dashboardApi = {
  overview: () => api.get<unknown, ApiResponse<OverviewData>>('/dashboard/overview'),
  yardUtilization: () => api.get<unknown, ApiResponse<YardUtilization[]>>('/dashboard/yard-utilization'),
  coalTypeInventory: () => api.get<unknown, ApiResponse<CoalTypeInventory[]>>('/dashboard/coal-type-inventory'),
  inOutTrend: (days = 30) => api.get<unknown, ApiResponse<InOutTrendItem[]>>('/dashboard/in-out-trend', { params: { days } }),
  agingAlert: (limit = 15) => api.get<unknown, ApiResponse<AgingAlertItem[]>>('/dashboard/aging-alert', { params: { limit } }),
  inventoryHistory: (days = 30) => api.get<unknown, ApiResponse<InventoryHistoryItem[]>>('/dashboard/inventory-history', { params: { days } }),
  blendingAdvice: (limit = 10) => api.get<unknown, ApiResponse<BlendingAdviceItem[]>>('/dashboard/blending-advice', { params: { limit } }),
  takeSnapshot: () => api.post<unknown, ApiResponse<null>>('/dashboard/snapshot'),
}

export default api
