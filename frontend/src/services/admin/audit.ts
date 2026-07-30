import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'

export interface AuditLogEntry {
  id: number
  actor_user_id: number | null
  actor_role: string | null
  action: string
  resource_type: string
  resource_id: string
  before_json: Record<string, unknown> | null
  after_json: Record<string, unknown> | null
  ip: string | null
  request_id: string | null
  created_at: string
}

export async function listAuditLogs(params: { resource_type?: string; actor_user_id?: number } = {}) {
  const { data } = await apiClient.get<Envelope<AuditLogEntry[]>>('/admin/audit-logs', { params })
  return data.data
}
