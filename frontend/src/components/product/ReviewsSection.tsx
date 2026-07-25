import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/feedback/Skeleton'
import { listReviews } from '@/services/review'
import { getApiErrorMessage } from '@/services/apiClient'
import { useCurrentUser } from '@/hooks/useAuth'
import { WriteReviewForm } from './WriteReviewForm'
import type { RatingBreakdownBucket } from '@/types/review'

const PER_PAGE = 10

function RatingBar({ bucket, total }: { bucket: RatingBreakdownBucket; total: number }) {
  const percent = total > 0 ? Math.round((bucket.count / total) * 100) : 0
  return (
    <div className="flex items-center gap-2 text-xs text-text-tertiary">
      <span className="w-3 text-right tabular-nums">{bucket.rating}</span>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="var(--text-tertiary)" aria-hidden="true">
        <path d="M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.8 5.8 21.2 7 14.2 2 9.3l7.1-.7z" />
      </svg>
      <div className="h-1.5 w-32 overflow-hidden rounded-full bg-surface-sunken sm:w-48">
        <div className="h-full rounded-full bg-text" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-8 tabular-nums">{bucket.count}</span>
    </div>
  )
}

interface ReviewsSectionProps {
  productSlug: string
}

export function ReviewsSection({ productSlug }: ReviewsSectionProps) {
  const { data: user } = useCurrentUser()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [writing, setWriting] = useState(false)

  const query = useQuery({
    // The response varies by viewer (an owner's own pending/rejected reviews are included, spec
    // §9.7) — without the viewer in the key, logging in/out after this query is already cached
    // would keep showing the previous viewer's version instead of refetching (caught live: Ada's
    // own pending review stayed invisible immediately after signing in on an already-loaded PDP).
    queryKey: ['reviews', productSlug, page, user?.public_id ?? 'guest'],
    queryFn: () => listReviews(productSlug, { page, per_page: PER_PAGE }),
  })

  return (
    <section id="reviews" className="mt-12 border-t border-border pt-8">
      <h2 className="text-lg font-semibold text-text">Reviews</h2>

      {query.isError ? (
        <p className="mt-4 text-sm text-danger">{getApiErrorMessage(query.error)}</p>
      ) : query.isLoading || !query.data ? (
        <div className="mt-4 space-y-2">
          <Skeleton className="h-16 w-full max-w-sm" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : (
        <>
          <div className="mt-4 flex flex-col gap-6 sm:flex-row sm:items-start sm:gap-10">
            <div className="shrink-0 text-center sm:text-left">
              <p className="text-4xl font-semibold tabular-nums text-text">
                {query.data.summary.rating_avg?.toFixed(1) ?? '—'}
              </p>
              <p className="mt-1 text-xs text-text-tertiary">
                {query.data.summary.rating_count} rating{query.data.summary.rating_count === 1 ? '' : 's'} ·{' '}
                {query.data.summary.review_count} review{query.data.summary.review_count === 1 ? '' : 's'}
              </p>
            </div>
            <div className="space-y-1.5">
              {query.data.summary.breakdown.map((bucket) => (
                <RatingBar key={bucket.rating} bucket={bucket} total={query.data.summary.rating_count} />
              ))}
            </div>
          </div>

          <div className="mt-6">
            {writing ? (
              <WriteReviewForm productSlug={productSlug} onDone={() => setWriting(false)} />
            ) : (
              <Button
                variant="secondary"
                onClick={() => {
                  if (!user) {
                    navigate(`/auth/login?next=${encodeURIComponent(window.location.pathname)}%23reviews`)
                    return
                  }
                  setWriting(true)
                }}
              >
                Write a review
              </Button>
            )}
          </div>

          {query.data.data.length === 0 ? (
            <p className="mt-8 text-sm text-text-tertiary">No reviews yet — be the first to share your experience.</p>
          ) : (
            <ul className="mt-8 divide-y divide-border">
              {query.data.data.map((review) => (
                <li key={review.id} className="py-5">
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-0.5" aria-hidden="true">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <svg
                          key={star}
                          width="13"
                          height="13"
                          viewBox="0 0 24 24"
                          fill={star <= review.rating ? 'var(--text)' : 'none'}
                          stroke="var(--text-tertiary)"
                          strokeWidth="1.5"
                        >
                          <path d="M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.8 5.8 21.2 7 14.2 2 9.3l7.1-.7z" />
                        </svg>
                      ))}
                    </span>
                    <span className="sr-only">{review.rating} out of 5 stars</span>
                    {review.title ? <span className="text-sm font-medium text-text">{review.title}</span> : null}
                  </div>
                  <p className="mt-1.5 text-xs text-text-tertiary">
                    {review.author_name}
                    {review.is_verified_purchase ? (
                      <span className="ml-2 rounded-full bg-surface-raised px-2 py-0.5 text-text-secondary">
                        Verified purchase
                      </span>
                    ) : null}
                    {review.is_own && review.status !== 'approved' ? (
                      <span className="ml-2 capitalize text-text-tertiary">({review.status})</span>
                    ) : null}
                    <span className="ml-2">{new Date(review.created_at).toLocaleDateString()}</span>
                  </p>
                  {review.comment ? (
                    <p className="mt-2 text-sm leading-relaxed text-text-secondary">{review.comment}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}

          {query.data.meta.total_pages > 1 ? (
            <div className="mt-6 flex items-center justify-between">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <span className="text-xs text-text-tertiary">
                Page {page} of {query.data.meta.total_pages}
              </span>
              <Button
                variant="secondary"
                size="sm"
                disabled={!query.data.meta.has_next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          ) : null}
        </>
      )}
    </section>
  )
}
