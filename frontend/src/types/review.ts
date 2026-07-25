export interface Review {
  id: number
  author_name: string
  rating: number
  title: string | null
  comment: string | null
  is_verified_purchase: boolean
  status: 'pending' | 'approved' | 'rejected' | 'hidden'
  helpful_count: number
  created_at: string
  is_own: boolean
}

export interface RatingBreakdownBucket {
  rating: number
  count: number
}

export interface ReviewSummary {
  rating_avg: number | null
  rating_count: number
  review_count: number
  breakdown: RatingBreakdownBucket[]
}

export interface ReviewListMeta {
  page: number
  per_page: number
  total: number
  total_pages: number
  has_next: boolean
}

export interface ReviewListResponse {
  data: Review[]
  meta: ReviewListMeta
  summary: ReviewSummary
}

export interface ReviewEligibleItem {
  order_item_id: number
  order_number: string
  title_snapshot: string
  image_snapshot: string | null
  delivered_at: string | null
}

export interface ReviewEligibility {
  can_review: boolean
  eligible_items: ReviewEligibleItem[]
  existing_review: Review | null
}

export interface AdminReview {
  id: number
  product_id: number
  product_slug: string
  product_title: string
  author_name: string
  rating: number
  title: string | null
  comment: string | null
  is_verified_purchase: boolean
  status: 'pending' | 'approved' | 'rejected' | 'hidden'
  helpful_count: number
  reported_count: number
  moderated_at: string | null
  created_at: string
}

export interface AdminReviewListResponse {
  data: AdminReview[]
  meta: ReviewListMeta
}
