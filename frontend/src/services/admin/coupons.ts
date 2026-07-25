import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type { Coupon, CouponInput } from '@/types/admin'

export async function listCoupons(): Promise<Coupon[]> {
  const { data } = await apiClient.get<Envelope<Coupon[]>>('/admin/coupons')
  return data.data
}

export async function getCoupon(id: number): Promise<Coupon> {
  const { data } = await apiClient.get<Envelope<Coupon>>(`/admin/coupons/${id}`)
  return data.data
}

export async function createCoupon(payload: CouponInput): Promise<Coupon> {
  const { data } = await apiClient.post<Envelope<Coupon>>('/admin/coupons', payload)
  return data.data
}

export async function updateCoupon(id: number, payload: CouponInput): Promise<Coupon> {
  const { data } = await apiClient.patch<Envelope<Coupon>>(`/admin/coupons/${id}`, payload)
  return data.data
}

export async function deactivateCoupon(id: number): Promise<Coupon> {
  const { data } = await apiClient.delete<Envelope<Coupon>>(`/admin/coupons/${id}`)
  return data.data
}
