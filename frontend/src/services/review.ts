import { apiClient } from './apiClient'
import type { Envelope } from '@/types/catalog'
import type { Review, ReviewEligibility, ReviewListResponse } from '@/types/review'

export async function listReviews(
  productSlug: string,
  params: { page?: number; per_page?: number } = {},
): Promise<ReviewListResponse> {
  const { data } = await apiClient.get<ReviewListResponse>(`/products/${productSlug}/reviews`, { params })
  return data
}

export async function getReviewEligibility(productSlug: string): Promise<ReviewEligibility> {
  const { data } = await apiClient.get<Envelope<ReviewEligibility>>(`/products/${productSlug}/reviews/eligibility`)
  return data.data
}

export interface ReviewInput {
  order_item_id: number
  rating: number
  title?: string
  comment?: string
}

export async function createReview(productSlug: string, payload: ReviewInput): Promise<Review> {
  const { data } = await apiClient.post<Envelope<Review>>(`/products/${productSlug}/reviews`, payload)
  return data.data
}

export async function updateReview(
  reviewId: number,
  payload: { rating: number; title?: string; comment?: string },
): Promise<Review> {
  const { data } = await apiClient.patch<Envelope<Review>>(`/reviews/${reviewId}`, payload)
  return data.data
}
