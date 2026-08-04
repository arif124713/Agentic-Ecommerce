import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listPages } from '@/services/admin/cms'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { cn } from '@/lib/cn'
import { SeoHead } from '@/components/seo/SeoHead'

export function CmsPagesListPage() {
  const query = useQuery({ queryKey: ['admin', 'cms', 'pages'], queryFn: listPages })

  return (
    <div>
      <SeoHead
        title="Manage CMS Pages"
        description="Create and manage static content pages published on BlackCart."
        path="/admin/cms/pages"
        noindex
      />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">CMS pages</h1>
        <Link
          to="/admin/cms/pages/new"
          className="flex h-10 items-center justify-center rounded-(--radius-md) bg-accent px-4 text-sm font-medium text-accent-fg hover:opacity-90"
        >
          + New page
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
          <EmptyState title="No CMS pages yet" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">Title</th>
                <th className="py-2 pr-4 font-medium">Slug</th>
                <th className="py-2 pr-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((p) => (
                <tr key={p.id} className={cn('hover:bg-surface-raised', p.is_deleted && 'opacity-50')}>
                  <td className="py-3 pr-4">
                    <Link to={`/admin/cms/pages/${p.id}`} className="font-medium text-text hover:underline">
                      {p.title}
                    </Link>
                    {p.is_deleted ? (
                      <span className="ml-2 rounded-full border border-danger/40 px-2 py-0.5 text-xs text-danger">
                        Deleted
                      </span>
                    ) : null}
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">/pages/{p.slug}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs capitalize',
                        p.status === 'published' ? 'border-border-strong text-text-secondary' : 'text-text-tertiary',
                      )}
                    >
                      {p.status}
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
