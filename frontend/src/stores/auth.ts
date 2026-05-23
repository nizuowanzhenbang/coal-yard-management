import { create } from 'zustand'

export type Role = 'ADMIN' | 'OPERATOR' | 'SUPERVISOR' | 'VIEWER'

interface AuthState {
  token: string | null
  username: string | null
  role: string | null
  setAuth: (token: string, username: string, role: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  username: localStorage.getItem('username'),
  role: localStorage.getItem('role'),
  setAuth: (token, username, role) => {
    localStorage.setItem('token', token)
    localStorage.setItem('username', username)
    localStorage.setItem('role', role)
    set({ token, username, role })
  },
  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
    set({ token: null, username: null, role: null })
  },
}))

/** 写操作：堆区登记 / 入场 / 出场 → ADMIN、OPERATOR */
export const canWrite = (role: string | null) =>
  role === 'ADMIN' || role === 'OPERATOR'

/** 审批操作：盘点审批 / 堆区停用 → ADMIN、SUPERVISOR */
export const canApprove = (role: string | null) =>
  role === 'ADMIN' || role === 'SUPERVISOR'

export const ROLE_LABEL: Record<string, string> = {
  ADMIN: '管理员',
  OPERATOR: '操作员',
  SUPERVISOR: '主管',
  VIEWER: '查看者',
}
