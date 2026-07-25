import { apiClient } from './apiClient'
import type { Envelope } from '@/types/catalog'
import type { CheckoutPreview, OrderDetail, OrderSummary, Tracking } from '@/types/order'

export interface CheckoutPayload {
  shipping_address_id: number
  billing_address_id?: number
  shipping_method: string
  payment_method: 'card' | 'cod'
  card_number?: string
  customer_note?: string
  accept_terms: boolean
}

export async function previewCheckout(
  payload: Omit<CheckoutPayload, 'accept_terms' | 'card_number' | 'customer_note'>,
): Promise<CheckoutPreview> {
  const { data } = await apiClient.post<Envelope<CheckoutPreview>>('/checkout/session', payload)
  return data.data
}

export async function createOrder(payload: CheckoutPayload): Promise<OrderDetail> {
  const { data } = await apiClient.post<Envelope<OrderDetail>>('/orders', payload, {
    headers: { 'Idempotency-Key': crypto.randomUUID() },
  })
  return data.data
}

export async function listOrders(): Promise<OrderSummary[]> {
  const { data } = await apiClient.get<Envelope<OrderSummary[]>>('/orders')
  return data.data
}

export async function getOrder(orderNumber: string): Promise<OrderDetail> {
  const { data } = await apiClient.get<Envelope<OrderDetail>>(`/orders/${orderNumber}`)
  return data.data
}

export async function getTracking(orderNumber: string): Promise<Tracking> {
  const { data } = await apiClient.get<Envelope<Tracking>>(`/orders/${orderNumber}/tracking`)
  return data.data
}

export async function cancelOrder(orderNumber: string, reason?: string): Promise<OrderDetail> {
  const { data } = await apiClient.post<Envelope<OrderDetail>>(`/orders/${orderNumber}/cancel`, { reason })
  return data.data
}
