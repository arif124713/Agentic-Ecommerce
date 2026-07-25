import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type { AdminOrderListItem } from '@/types/admin'
import type { OrderDetail } from '@/types/order'

export async function listAdminOrders(params: { status?: string; q?: string; page?: number; per_page?: number } = {}) {
  const { data } = await apiClient.get<Envelope<AdminOrderListItem[]>>('/admin/orders', { params })
  return data.data
}

export async function getAdminOrder(orderNumber: string): Promise<OrderDetail> {
  const { data } = await apiClient.get<Envelope<OrderDetail>>(`/admin/orders/${orderNumber}`)
  return data.data
}

export async function transitionOrder(orderNumber: string, toStatus: string, reason?: string): Promise<OrderDetail> {
  const { data } = await apiClient.post<Envelope<OrderDetail>>(`/admin/orders/${orderNumber}/transition`, {
    to_status: toStatus,
    reason,
  })
  return data.data
}

export interface RefundResult {
  transaction_id: string
  amount: string
  status: string
  processed_at: string | null
}

export async function refundOrder(orderNumber: string, amount: string, reason?: string): Promise<RefundResult> {
  const { data } = await apiClient.post<Envelope<RefundResult>>(`/admin/orders/${orderNumber}/refund`, {
    amount,
    reason,
  })
  return data.data
}
