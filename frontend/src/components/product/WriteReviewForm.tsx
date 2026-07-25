import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { StarRatingInput } from './StarRatingInput'
import { createReview, getReviewEligibility, updateReview } from '@/services/review'
import { getApiErrorMessage } from '@/services/apiClient'
import type { Review } from '@/types/review'

interface WriteReviewFormProps {
  productSlug: string
  onDone: () => void
}

const EDIT_WINDOW_MS = 24 * 60 * 60 * 1000

function EditOwnReview({ review, onDone }: { review: Review; onDone: () => void }) {
  const queryClient = useQueryClient()
  const [rating, setRating] = useState(review.rating)
  const [title, setTitle] = useState(review.title ?? '')
  const [comment, setComment] = useState(review.comment ?? '')
  const editable = Date.now() - new Date(review.created_at).getTime() < EDIT_WINDOW_MS

  const mutation = useMutation({
    mutationFn: () => updateReview(review.id, { rating, title: title.trim() || undefined, comment: comment.trim() || undefined }),
    onSuccess: () => {
      toast.success('Review updated — it will show again once re-approved.')
      queryClient.invalidateQueries({ queryKey: ['reviews'] })
      onDone()
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  return (
    <div className="rounded-(--radius-lg) border border-border bg-surface p-5">
      <p className="text-sm font-medium text-text">Your review</p>
      <p className="mt-1 text-xs text-text-tertiary">
        Status: <span className="capitalize">{review.status}</span>
        {editable ? ' · editable for a little while longer' : ' · edit window has closed'}
      </p>
      {editable ? (
        <form
          className="mt-4 space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            mutation.mutate()
          }}
        >
          {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}
          <StarRatingInput value={rating} onChange={setRating} />
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title (optional)"
            maxLength={150}
            className="h-11 w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          />
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Your review (optional)"
            rows={3}
            maxLength={2000}
            className="w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
          />
          <div className="flex gap-3">
            <Button type="submit" loading={mutation.isPending}>
              Save changes
            </Button>
            <Button type="button" variant="ghost" onClick={onDone}>
              Close
            </Button>
          </div>
        </form>
      ) : (
        <Button type="button" variant="secondary" className="mt-4" onClick={onDone}>
          Close
        </Button>
      )}
    </div>
  )
}

export function WriteReviewForm({ productSlug, onDone }: WriteReviewFormProps) {
  const queryClient = useQueryClient()
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)
  const [rating, setRating] = useState(0)
  const [title, setTitle] = useState('')
  const [comment, setComment] = useState('')

  const eligibilityQuery = useQuery({
    queryKey: ['reviews', 'eligibility', productSlug],
    queryFn: () => getReviewEligibility(productSlug),
  })

  const mutation = useMutation({
    mutationFn: (orderItemId: number) =>
      createReview(productSlug, { order_item_id: orderItemId, rating, title: title.trim() || undefined, comment: comment.trim() || undefined }),
    onSuccess: () => {
      toast.success('Thanks — your review is awaiting approval.')
      queryClient.invalidateQueries({ queryKey: ['reviews'] })
      queryClient.invalidateQueries({ queryKey: ['reviews', 'eligibility', productSlug] })
      onDone()
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  if (eligibilityQuery.isLoading) {
    return <p className="text-sm text-text-tertiary">Checking your purchase history…</p>
  }

  const eligibility = eligibilityQuery.data

  if (eligibility?.existing_review) {
    return <EditOwnReview review={eligibility.existing_review} onDone={onDone} />
  }

  if (!eligibility?.can_review) {
    return (
      <div className="rounded-(--radius-lg) border border-border bg-surface p-5 text-sm text-text-secondary">
        Only customers with a delivered order for this product can leave a review.
      </div>
    )
  }

  const items = eligibility.eligible_items
  const activeItemId = selectedItemId ?? items[0]?.order_item_id ?? null

  return (
    <form
      className="space-y-4 rounded-(--radius-lg) border border-border bg-surface p-5"
      onSubmit={(e) => {
        e.preventDefault()
        if (!activeItemId || rating < 1) return
        mutation.mutate(activeItemId)
      }}
    >
      <p className="text-sm font-medium text-text">Write a review</p>
      {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}

      {items.length > 1 ? (
        <div>
          <label htmlFor="review-order-item" className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
            Which order was this?
          </label>
          <select
            id="review-order-item"
            value={activeItemId ?? ''}
            onChange={(e) => setSelectedItemId(Number(e.target.value))}
            className="mt-1 h-11 w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
          >
            {items.map((item) => (
              <option key={item.order_item_id} value={item.order_item_id}>
                {item.order_number}
                {item.delivered_at ? ` — delivered ${new Date(item.delivered_at).toLocaleDateString()}` : ''}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Your rating</p>
        <div className="mt-1">
          <StarRatingInput value={rating} onChange={setRating} />
        </div>
      </div>

      <label htmlFor="review-title" className="sr-only">
        Review title
      </label>
      <input
        id="review-title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (optional)"
        maxLength={150}
        className="h-11 w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />

      <label htmlFor="review-comment" className="sr-only">
        Review comment
      </label>
      <textarea
        id="review-comment"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Share details of your experience with this product (optional)"
        rows={4}
        maxLength={2000}
        className="w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />

      <div className="flex gap-3">
        <Button type="submit" loading={mutation.isPending} disabled={rating < 1}>
          Submit review
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
