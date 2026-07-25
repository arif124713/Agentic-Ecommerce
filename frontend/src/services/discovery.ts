import { apiClient } from './apiClient'
import type { Envelope, ProductCard } from '@/types/catalog'
import type { Wishlist } from '@/types/discovery'

export async function getWishlist(): Promise<Wishlist> {
  const { data } = await apiClient.get<Envelope<Wishlist>>('/wishlist')
  return data.data
}

export async function getWishlistSlugs(): Promise<string[]> {
  const { data } = await apiClient.get<Envelope<string[]>>('/wishlist/slugs')
  return data.data
}

export async function addWishlistItem(productSlug: string): Promise<Wishlist> {
  const { data } = await apiClient.post<Envelope<Wishlist>>('/wishlist/items', { product_slug: productSlug })
  return data.data
}

export async function removeWishlistItem(productSlug: string): Promise<Wishlist> {
  const { data } = await apiClient.delete<Envelope<Wishlist>>(`/wishlist/items/${productSlug}`)
  return data.data
}

export async function getRecentlyViewed(): Promise<ProductCard[]> {
  const { data } = await apiClient.get<Envelope<ProductCard[]>>('/recently-viewed')
  return data.data
}

export async function recordProductView(slug: string): Promise<void> {
  await apiClient.post(`/products/${slug}/view`)
}

export async function getSimilarProducts(slug: string): Promise<ProductCard[]> {
  const { data } = await apiClient.get<Envelope<ProductCard[]>>(`/products/${slug}/similar`)
  return data.data
}

export async function getFrequentlyBoughtTogether(slug: string): Promise<ProductCard[]> {
  const { data } = await apiClient.get<Envelope<ProductCard[]>>(`/products/${slug}/frequently-bought-together`)
  return data.data
}

export async function subscribeStockAlert(
  slug: string,
  payload: { variant_id: number; email?: string },
): Promise<void> {
  await apiClient.post(`/products/${slug}/stock-alerts`, payload)
}

export async function subscribeNewsletter(email: string): Promise<void> {
  await apiClient.post('/newsletter/subscribe', { email })
}
