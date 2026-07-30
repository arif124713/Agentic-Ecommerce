import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listAuditLogs } from '@/services/admin/audit'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'

const RESOURCE_TYPES = ['all', 'product', 'product_variant', 'order', 'user', 'coupon', 'cms_page', 'banner', 'support_ticket', 'feature_flag']

function DiffCell({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) {
  return (
    <div className="flex flex-col gap-1 font-mono text-xs">
      {before ? <div className="text-danger/80">- {JSON.stringify(before)}</div> : null}
      {after ? <div className="text-success/80">+ {JSON.stringify(after)}</div> : null}
    </div>
  )
}

export function AuditLogsPage() {
  const [resourceType, setResourceType] = useState('all')
  const query = useQuery({
    queryKey: ['admin', 'audit-logs', resourceType],
    queryFn: () => listAuditLogs(resourceType === 'all' ? {} : { resource_type: resourceType }),
  })

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Audit logs</h1>
      <p className="mt-1 text-sm text-text-tertiary">
        Every admin mutation writes a row here with a before/after diff — append-only.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {RESOURCE_TYPES.map((rt) => (
          <button
            key={rt}
            type="button"
            onClick={() => setResourceType(rt)}
            className={
              'rounded-full border px-3 py-1.5 text-xs ' +
              (resourceType === rt
                ? 'border-text bg-text text-bg'
                : 'border-border text-text-secondary hover:bg-surface-raised')
            }
          >
            {rt}
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
          <EmptyState title="No audit log entries yet" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">When</th>
                <th className="py-2 pr-4 font-medium">Actor</th>
                <th className="py-2 pr-4 font-medium">Action</th>
                <th className="py-2 pr-4 font-medium">Resource</th>
                <th className="py-2 pr-4 font-medium">Diff</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((log) => (
                <tr key={log.id}>
                  <td className="py-3 pr-4 whitespace-nowrap text-text-tertiary">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">
                    #{log.actor_user_id ?? '—'}
                    {log.actor_role ? <span className="text-text-tertiary"> ({log.actor_role})</span> : null}
                  </td>
                  <td className="py-3 pr-4 font-medium text-text">{log.action}</td>
                  <td className="py-3 pr-4 text-text-secondary">
                    {log.resource_type}:{log.resource_id}
                  </td>
                  <td className="py-3 pr-4">
                    <DiffCell before={log.before_json} after={log.after_json} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
