import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type { DashboardSummary } from '@/types/admin'

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<Envelope<DashboardSummary>>('/admin/dashboard/summary')
  return data.data
}
