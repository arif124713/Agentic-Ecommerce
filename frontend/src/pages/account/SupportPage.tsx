import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { EmptyState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { createTicket, listMyTickets } from '@/services/support'
import { SeoHead } from '@/components/seo/SeoHead'

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  pending: 'Pending',
  resolved: 'Resolved',
  closed: 'Closed',
}

function NewTicketForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [priority, setPriority] = useState<'low' | 'medium' | 'high'>('medium')

  const mutation = useMutation({
    mutationFn: () => createTicket({ subject: subject.trim(), body: body.trim(), priority }),
    onSuccess: () => {
      toast.success('Ticket submitted — we’ll get back to you soon.')
      queryClient.invalidateQueries({ queryKey: ['support', 'tickets'] })
      onDone()
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  return (
    <form
      className="space-y-4 rounded-(--radius-lg) border border-border bg-surface p-5"
      onSubmit={(e) => {
        e.preventDefault()
        if (!subject.trim() || !body.trim()) return
        mutation.mutate()
      }}
    >
      <p className="text-sm font-medium text-text">New support ticket</p>
      {mutation.isError ? <FormAlert>{getApiErrorMessage(mutation.error)}</FormAlert> : null}

      <label htmlFor="ticket-subject" className="sr-only">
        Subject
      </label>
      <input
        id="ticket-subject"
        value={subject}
        onChange={(e) => setSubject(e.target.value)}
        placeholder="Subject"
        maxLength={255}
        required
        className="h-11 w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />

      <label htmlFor="ticket-priority" className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
        Priority
      </label>
      <select
        id="ticket-priority"
        value={priority}
        onChange={(e) => setPriority(e.target.value as typeof priority)}
        className="h-11 w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
      >
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>

      <label htmlFor="ticket-body" className="sr-only">
        Describe your issue
      </label>
      <textarea
        id="ticket-body"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Describe your issue…"
        rows={5}
        required
        maxLength={4000}
        className="w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 py-2 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />

      <div className="flex gap-3">
        <Button type="submit" loading={mutation.isPending} disabled={!subject.trim() || !body.trim()}>
          Submit ticket
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function SupportPage() {
  const [showForm, setShowForm] = useState(false)
  const query = useQuery({ queryKey: ['support', 'tickets'], queryFn: listMyTickets })

  return (
    <div className="container-page max-w-2xl py-10">
      <SeoHead
        title="Support"
        description="View your support tickets or open a new one with the BlackCart team."
        path="/account/support"
        noindex
      />
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">Support</h1>
        {!showForm ? <Button onClick={() => setShowForm(true)}>New ticket</Button> : null}
      </div>

      {showForm ? (
        <div className="mt-8">
          <NewTicketForm onDone={() => setShowForm(false)} />
        </div>
      ) : null}

      <div className="mt-8">
        {query.isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : query.data && query.data.length === 0 ? (
          !showForm ? (
            <EmptyState
              title="No support tickets yet"
              description="Something wrong with an order, or a question for us? Open a ticket and we'll help."
              action={<Button onClick={() => setShowForm(true)}>New ticket</Button>}
            />
          ) : null
        ) : (
          <ul className="flex flex-col divide-y divide-border rounded-(--radius-lg) border border-border">
            {query.data?.map((ticket) => (
              <li key={ticket.public_id}>
                <Link
                  to={`/account/support/${ticket.public_id}`}
                  className="flex items-center justify-between gap-4 px-5 py-4 hover:bg-surface-raised"
                >
                  <div>
                    <p className="text-sm font-medium text-text">{ticket.subject}</p>
                    <p className="text-xs text-text-tertiary">
                      Updated {new Date(ticket.updated_at).toLocaleString()}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full bg-surface-raised px-3 py-1 text-xs capitalize text-text-secondary">
                    {STATUS_LABEL[ticket.status] ?? ticket.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
