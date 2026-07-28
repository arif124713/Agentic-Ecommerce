import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listBanners } from '@/services/admin/cms'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { cn } from '@/lib/cn'

export function BannersListPage() {
  const query = useQuery({ queryKey: ['admin', 'cms', 'banners'], queryFn: listBanners })

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Banners</h1>
        <Link
          to="/admin/cms/banners/new"
          className="flex h-10 items-center justify-center rounded-(--radius-md) bg-accent px-4 text-sm font-medium text-accent-fg hover:opacity-90"
        >
          + New banner
        </Link>
      </div>

      {query.isError ? (
        <div className="mt-8">
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        </div>
      ) : query.isLoading || !query.data ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : query.data.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No banners yet" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">Title</th>
                <th className="py-2 pr-4 font-medium">Placement</th>
                <th className="py-2 pr-4 font-medium">Sort</th>
                <th className="py-2 pr-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((b) => (
                <tr key={b.id} className="hover:bg-surface-raised">
                  <td className="py-3 pr-4">
                    <Link to={`/admin/cms/banners/${b.id}`} className="font-medium text-text hover:underline">
                      {b.title}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">{b.placement}</td>
                  <td className="py-3 pr-4 tabular-nums text-text-secondary">{b.sort_order}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs',
                        b.is_active ? 'border-border-strong text-text-secondary' : 'border-danger/40 text-danger',
                      )}
                    >
                      {b.is_active ? 'Active' : 'Inactive'}
                    </span>
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
