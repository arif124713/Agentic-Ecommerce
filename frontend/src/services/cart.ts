import { apiClient } from './apiClient'
import type { Cart } from '@/types/cart'
import type { Envelope } from '@/types/catalog'

export async function getCart(): Promise<Cart> {
  const { data } = await apiClient.get<Envelope<Cart>>('/cart')
  return data.data
}

export async function addCartItem(variantId: number, quantity: number): Promise<Cart> {
  const { data } = await apiClient.post<Envelope<Cart>>('/cart/items', { variant_id: variantId, quantity })
  return data.data
}

export async function updateCartItem(itemId: number, quantity: number): Promise<Cart> {
  const { data } = await apiClient.patch<Envelope<Cart>>(`/cart/items/${itemId}`, { quantity })
  return data.data
}

export async function removeCartItem(itemId: number): Promise<Cart> {
  const { data } = await apiClient.delete<Envelope<Cart>>(`/cart/items/${itemId}`)
  return data.data
}

export async function clearCart(): Promise<Cart> {
  const { data } = await apiClient.delete<Envelope<Cart>>('/cart')
  return data.data
}

export async function applyCoupon(code: string): Promise<Cart> {
  const { data } = await apiClient.post<Envelope<Cart>>('/cart/coupon', { code })
  return data.data
}

export async function removeCoupon(): Promise<Cart> {
  const { data } = await apiClient.delete<Envelope<Cart>>('/cart/coupon')
  return data.data
}
