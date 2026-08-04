import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listAllTickets } from '@/services/admin/support'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { cn } from '@/lib/cn'
import { SeoHead } from '@/components/seo/SeoHead'

const STATUS_FILTERS = ['all', 'open', 'pending', 'resolved', 'closed'] as const

export function SupportQueuePage() {
  const [status, setStatus] = useState<(typeof STATUS_FILTERS)[number]>('all')
  const query = useQuery({
    queryKey: ['admin', 'support', 'tickets', status],
    queryFn: () => listAllTickets(status === 'all' ? undefined : { status }),
  })

  return (
    <div>
      <SeoHead
        title="Support Queue"
        description="View and manage customer support tickets submitted to BlackCart."
        path="/admin/support"
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">Support tickets</h1>

      <div className="mt-4 flex gap-2">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatus(s)}
            className={cn(
              'rounded-full border px-3 py-1.5 text-xs capitalize',
              status === s ? 'border-text bg-text text-bg' : 'border-border text-text-secondary hover:bg-surface-raised',
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {query.isError ? (
        <div className="mt-8">
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        </div>
      ) : query.isLoading || !query.data ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : query.data.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No tickets here" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">Subject</th>
                <th className="py-2 pr-4 font-medium">Customer</th>
                <th className="py-2 pr-4 font-medium">Priority</th>
                <th className="py-2 pr-4 font-medium">Assignee</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((t) => (
                <tr key={t.public_id} className="hover:bg-surface-raised">
                  <td className="py-3 pr-4">
                    <Link to={`/admin/support/${t.public_id}`} className="font-medium text-text hover:underline">
                      {t.subject}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">{t.contact_email}</td>
                  <td className="py-3 pr-4 capitalize text-text-secondary">{t.priority}</td>
                  <td className="py-3 pr-4 text-text-secondary">{t.assignee_name ?? '—'}</td>
                  <td className="py-3 pr-4">
                    <span className="rounded-full border border-border-strong px-2 py-0.5 text-xs capitalize text-text-secondary">
                      {t.status}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-text-tertiary">{new Date(t.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
