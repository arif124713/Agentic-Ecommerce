import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { cn } from '@/lib/cn'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { assignTicket, getAdminTicket, replyAsStaff, updateTicketStatus } from '@/services/admin/support'
import { SeoHead } from '@/components/seo/SeoHead'

const STATUSES = ['open', 'pending', 'resolved', 'closed'] as const

export function AdminTicketDetailPage() {
  const { publicId = '' } = useParams<{ publicId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [reply, setReply] = useState('')
  const [assigneeInput, setAssigneeInput] = useState('')

  const queryKey = ['admin', 'support', 'tickets', publicId]
  const query = useQuery({ queryKey, queryFn: () => getAdminTicket(publicId), retry: false })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey })
    queryClient.invalidateQueries({ queryKey: ['admin', 'support', 'tickets'] })
  }

  const replyMutation = useMutation({
    mutationFn: () => replyAsStaff(publicId, reply.trim()),
    onSuccess: () => {
      setReply('')
      invalidate()
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  const statusMutation = useMutation({
    mutationFn: (status: string) => updateTicketStatus(publicId, status),
    onSuccess: invalidate,
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  const assignMutation = useMutation({
    mutationFn: (assigneeUserId: number | null) => assignTicket(publicId, assigneeUserId),
    onSuccess: () => {
      setAssigneeInput('')
      invalidate()
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  if (query.isLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  if (query.isError) {
    return (
      <EmptyState
        title="Ticket not found"
        action={
          <Link to="/admin/support">
            <Button variant="secondary">Back to queue</Button>
          </Link>
        }
      />
    )
  }

  const ticket = query.data!

  return (
    <div className="max-w-2xl">
      <SeoHead
        title="Support Ticket"
        description="View and respond to a customer support ticket submitted to BlackCart."
        path={location.pathname}
        noindex
      />
      <button type="button" onClick={() => navigate(-1)} className="text-sm text-text-secondary hover:text-text">
        ← Back
      </button>

      <div className="mt-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-text">{ticket.subject}</h1>
          <p className="mt-1 text-sm text-text-tertiary">{ticket.contact_email}</p>
        </div>
        <select
          value={ticket.status}
          onChange={(e) => statusMutation.mutate(e.target.value)}
          disabled={statusMutation.isPending}
          className="h-10 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm capitalize text-text"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4 flex items-center gap-3 rounded-(--radius-md) border border-border p-3 text-sm">
        <span className="text-text-tertiary">Assigned to:</span>
        <span className="font-medium text-text">{ticket.assignee_name ?? 'Unassigned'}</span>
        <input
          value={assigneeInput}
          onChange={(e) => setAssigneeInput(e.target.value)}
          placeholder="User ID"
          className="ml-auto h-9 w-24 rounded-(--radius-md) border border-border bg-surface-sunken px-2 text-sm text-text"
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          loading={assignMutation.isPending}
          onClick={() => assignMutation.mutate(assigneeInput ? Number(assigneeInput) : null)}
        >
          {assigneeInput ? 'Assign' : 'Unassign'}
        </Button>
      </div>

      <div className="mt-8 flex flex-col gap-4">
        {ticket.messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              'max-w-[85%] rounded-(--radius-lg) border p-4 text-sm',
              message.author_type === 'staff'
                ? 'self-end border-border-strong bg-surface text-text'
                : 'self-start border-border bg-surface-raised text-text',
            )}
          >
            <p className="mb-1 text-xs font-medium text-text-tertiary">
              {message.author_type === 'staff' ? 'Support team' : 'Customer'} ·{' '}
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
          replyMutation.mutate()
        }}
      >
        {replyMutation.isError ? <FormAlert>{getApiErrorMessage(replyMutation.error)}</FormAlert> : null}
        <label htmlFor="staff-reply" className="sr-only">
          Reply
        </label>
        <textarea
          id="staff-reply"
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder="Reply to the customer…"
          rows={4}
          maxLength={4000}
          className="w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
        />
        <Button type="submit" loading={replyMutation.isPending} disabled={!reply.trim()}>
          Send reply
        </Button>
      </form>
    </div>
  )
}
