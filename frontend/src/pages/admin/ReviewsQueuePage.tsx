import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { listAdminReviews, moderateReview } from '@/services/admin/reviews'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import { SeoHead } from '@/components/seo/SeoHead'

const STATUSES = ['pending', 'approved', 'rejected', 'hidden'] as const

export function ReviewsQueuePage() {
  const [status, setStatus] = useState<string>('pending')
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['admin', 'reviews', status],
    queryFn: () => listAdminReviews({ status: status || undefined, per_page: 50 }),
  })

  const moderateMutation = useMutation({
    mutationFn: ({ id, next }: { id: number; next: 'approved' | 'rejected' | 'hidden' }) => moderateReview(id, next),
    onSuccess: (review) => {
      toast.success(`Review marked ${review.status}.`)
      queryClient.invalidateQueries({ queryKey: ['admin', 'reviews'] })
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  return (
    <div>
      <SeoHead
        title="Review Queue"
        description="Moderate customer product reviews submitted to BlackCart."
        path="/admin/reviews"
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">Reviews</h1>

      <div className="mt-6 flex gap-3">
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
          className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {query.isError ? (
        <div className="mt-8">
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        </div>
      ) : query.isLoading || !query.data ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : query.data.data.length === 0 ? (
        <div className="mt-8">
          <EmptyState title={`No ${status || ''} reviews`.trim()} />
        </div>
      ) : (
        <ul className="mt-6 divide-y divide-border">
          {query.data.data.map((review) => {
            const isPending = moderateMutation.isPending && moderateMutation.variables?.id === review.id
            return (
              <li key={review.id} className="py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm">
                      <Link to={`/p/${review.product_slug}`} target="_blank" className="font-medium text-text hover:underline">
                        {review.product_title}
                      </Link>
                      <span
                        className={cn(
                          'rounded-full border px-2 py-0.5 text-xs capitalize',
                          review.status === 'approved' && 'border-success/40 text-success',
                          review.status === 'pending' && 'border-border-strong text-text-secondary',
                          (review.status === 'rejected' || review.status === 'hidden') && 'border-danger/40 text-danger',
                        )}
                      >
                        {review.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-text-tertiary">
                      {review.author_name} · {review.rating}/5
                      {review.is_verified_purchase ? ' · Verified purchase' : ''} ·{' '}
                      {new Date(review.created_at).toLocaleDateString()}
                    </p>
                    {review.title ? <p className="mt-2 text-sm font-medium text-text">{review.title}</p> : null}
                    {review.comment ? (
                      <p className="mt-1 max-w-2xl text-sm text-text-secondary">{review.comment}</p>
                    ) : null}
                  </div>

                  <div className="flex shrink-0 gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={review.status === 'approved' || isPending}
                      onClick={() => moderateMutation.mutate({ id: review.id, next: 'approved' })}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={review.status === 'rejected' || isPending}
                      onClick={() => moderateMutation.mutate({ id: review.id, next: 'rejected' })}
                    >
                      Reject
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={review.status === 'hidden' || isPending}
                      onClick={() => moderateMutation.mutate({ id: review.id, next: 'hidden' })}
                    >
                      Hide
                    </Button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
