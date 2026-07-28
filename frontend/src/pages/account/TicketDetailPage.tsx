import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { cn } from '@/lib/cn'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { getTicket, replyToTicket } from '@/services/support'

export function TicketDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [reply, setReply] = useState('')

  const query = useQuery({
    queryKey: ['support', 'tickets', publicId],
    queryFn: () => getTicket(publicId),
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: () => replyToTicket(publicId, reply.trim()),
    onSuccess: () => {
      setReply('')
      queryClient.invalidateQueries({ queryKey: ['support', 'tickets', publicId] })
      queryClient.invalidateQueries({ queryKey: ['support', 'tickets'] })
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  if (query.isLoading) {
    return (
      <div className="container-page max-w-2xl py-10">
        <Skeleton className="h-9 w-2/3" />
        <Skeleton className="mt-6 h-32 w-full" />
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="container-page max-w-2xl py-10">
        <EmptyState
          title="Ticket not found"
          description="This ticket doesn't exist, or isn't yours."
          action={
            <Link to="/account/support">
              <Button variant="secondary">Back to support</Button>
            </Link>
          }
        />
      </div>
    )
  }

  const ticket = query.data!
  const closed = ticket.status === 'resolved' || ticket.status === 'closed'

  return (
    <div className="container-page max-w-2xl py-10">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="text-sm text-text-secondary hover:text-text"
      >
        ← Back
      </button>

      <div className="mt-4 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight text-text">{ticket.subject}</h1>
        <span className="shrink-0 rounded-full bg-surface-raised px-3 py-1 text-xs capitalize text-text-secondary">
          {ticket.status}
        </span>
      </div>

      <div className="mt-8 flex flex-col gap-4">
        {ticket.messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'max-w-[85%] rounded-(--radius-lg) border p-4 text-sm',
              message.author_type === 'staff'
                ? 'self-start border-border bg-surface-raised text-text'
                : 'self-end border-border-strong bg-surface text-text',
            )}
          >
            <p className="mb-1 text-xs font-medium text-text-tertiary">
              {message.author_type === 'staff' ? 'Support team' : 'You'} ·{' '}
              {new Date(message.created_at).toLocaleString()}
            </p>
            <p className="whitespace-pre-wrap leading-relaxed">{message.body}</p>
          </div>
        ))}
      </div>

      <form
        className="mt-8 space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (!reply.trim()) return
          mutation.mutate()
        }}
      >
        {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}
        {closed ? (
          <p className="text-xs text-text-tertiary">
            This ticket is {ticket.status}. Sending a message will reopen it.
          </p>
        ) : null}
        <label htmlFor="ticket-reply" className="sr-only">
          Reply
        </label>
        <textarea
          id="ticket-reply"
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder="Write a reply…"
          rows={3}
          maxLength={4000}
          className="w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
        />
        <Button type="submit" loading={mutation.isPending} disabled={!reply.trim()}>
          Send reply
        </Button>
      </form>
    </div>
  )
}
