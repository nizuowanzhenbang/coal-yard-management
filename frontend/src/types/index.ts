export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type UserRole = 'ADMIN' | 'OPERATOR' | 'SUPERVISOR' | 'VIEWER'

export type YardStatus = 'ACTIVE' | 'MAINTENANCE' | 'DISABLED'

export interface CoalYard {
  id: number
  code: string
  name: string
  designated_coal_type: string
  capacity: number
  location: string | null
  longitude: number | null
  latitude: number | null
  status: YardStatus
  notes: string | null
  created_at: string
  updated_at: string
  current_inventory: number | null
  utilization: number | null
  oldest_in_days: number | null
}

export interface CoalYardDetail extends CoalYard {
  aging_summary: { green: number; yellow: number; red: number }
  batch_count: number
}

export interface StockIn {
  id: number
  stockin_no: string
  yard_id: number
  yard_code: string | null
  yard_name: string | null
  order_no: string | null
  supplier_name: string | null
  contract_no: string | null
  coal_type: string
  quantity: number
  remaining_quantity: number
  calorific_value: number | null
  ash: number | null
  sulfur: number | null
  moisture: number | null
  quality_synced: boolean
  stocked_at: string
  operator: string | null
  transport_mode: string | null
  notes: string | null
  created_at: string
  aging_days: number | null
}

export type StockOutStatus = 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'COMPLETED'

export interface StockOut {
  id: number
  stockout_no: string
  yard_id: number
  yard_code: string | null
  yard_name: string | null
  coal_type: string
  quantity: number
  destination: string
  purpose: string | null
  delivered_at: string
  operator: string | null
  fifo_breakdown: string | null
  requires_approval: boolean
  status: StockOutStatus
  approver: string | null
  approved_at: string | null
  approval_notes: string | null
  notes: string | null
  created_at: string
}

export type StocktakeStatus = 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED'

export interface Stocktake {
  id: number
  stocktake_no: string
  yard_id: number
  yard_code: string | null
  yard_name: string | null
  book_inventory: number
  actual_inventory: number
  diff_quantity: number
  diff_rate: number
  measured_at: string
  measurer: string | null
  method: string | null
  reason: string | null
  status: StocktakeStatus
  approver: string | null
  approved_at: string | null
  approval_notes: string | null
  created_at: string
}

// Dashboard
export interface OverviewData {
  active_yards: number
  total_capacity: number
  total_inventory: number
  utilization: number
  today_in_tons: number
  today_out_tons: number
  pending_stocktakes: number
  aging_danger_tons: number
  hot_spots_24h: number
}

// v2: 温度监控
export type TemperatureSource = 'MANUAL' | 'SENSOR' | 'THERMAL_IMAGE'
export type TempLevel = 'green' | 'warn' | 'alert' | 'danger'

export interface TemperatureReading {
  id: number
  yard_id: number
  yard_code: string | null
  yard_name: string | null
  spot: string
  temperature: number
  source: TemperatureSource
  measured_at: string
  operator: string | null
  notes: string | null
  created_at: string
  level: TempLevel
}

export interface TempTrendItem {
  date: string
  max_temp: number
  avg_temp: number
  min_temp: number
  samples: number
}

// v2: 入煤综合评分 + 配煤建议
export interface ScoreBreakdown {
  calorific_score: number
  ash_penalty: number
  sulfur_penalty: number
  moisture_penalty: number
  base_score: number
  aging_decay: number
  current_score: number
}

export interface StockInDetail extends StockIn {
  score: number
  score_breakdown: ScoreBreakdown
}

export interface BlendingAdviceItem {
  stockin_no: string
  yard_code: string | null
  yard_name: string | null
  coal_type: string
  remaining_quantity: number
  calorific_value: number | null
  aging_days: number
  current_score: number
  base_score: number
  aging_decay: number
  priority: number
}

export interface YardUtilization {
  yard_code: string
  yard_name: string
  coal_type: string
  capacity: number
  inventory: number
  utilization: number
  status: string
}

export interface CoalTypeInventory {
  coal_type: string
  inventory: number
}

export interface InOutTrendItem {
  date: string
  in: number
  out: number
}

export interface AgingAlertItem {
  stockin_no: string
  yard_code: string | null
  yard_name: string | null
  coal_type: string
  supplier_name: string | null
  stocked_at: string
  aging_days: number
  remaining_quantity: number
  level: 'green' | 'yellow' | 'red'
}

export interface InventoryHistoryItem {
  date: string
  inventory: number
}
