import { apiClient } from '../apiClient'
import type { Envelope } from '@/types/catalog'
import type { AdminReview, AdminReviewListResponse } from '@/types/review'

export async function listAdminReviews(
  params: { status?: string; page?: number; per_page?: number } = {},
): Promise<AdminReviewListResponse> {
  const { data } = await apiClient.get<AdminReviewListResponse>('/admin/reviews', { params })
  return data
}

export async function moderateReview(
  reviewId: number,
  status: 'approved' | 'rejected' | 'hidden',
): Promise<AdminReview> {
  const { data } = await apiClient.post<Envelope<AdminReview>>(`/admin/reviews/${reviewId}/moderate`, { status })
  return data.data
}
