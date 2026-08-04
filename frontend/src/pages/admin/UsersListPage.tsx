import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listAdminUsers } from '@/services/admin/users'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { cn } from '@/lib/cn'
import { SeoHead } from '@/components/seo/SeoHead'

export function UsersListPage() {
  const [q, setQ] = useState('')
  const query = useQuery({
    queryKey: ['admin', 'users', q],
    queryFn: () => listAdminUsers({ q: q || undefined, per_page: 50 }),
  })

  return (
    <div>
      <SeoHead
        title="Manage Users"
        description="Search and manage BlackCart customer accounts, roles, and access."
        path="/admin/users"
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">Users</h1>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search by name or email…"
        aria-label="Search users by name or email"
        className="mt-6 h-11 w-full max-w-md rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      />

      {query.isError ? (
        <div className="mt-8">
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        </div>
      ) : query.isLoading || !query.data ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : query.data.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No users found" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Email</th>
                <th className="py-2 pr-4 font-medium">Roles</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((u) => (
                <tr key={u.public_id} className="hover:bg-surface-raised">
                  <td className="py-3 pr-4">
                    <Link to={`/admin/users/${u.public_id}`} className="font-medium text-text hover:underline">
                      {u.first_name} {u.last_name ?? ''}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">{u.email}</td>
                  <td className="py-3 pr-4 text-text-secondary">{u.roles.join(', ')}</td>
                  <td className="py-3 pr-4">
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs capitalize',
                        u.status === 'active' ? 'border-border-strong text-text-secondary' : 'border-danger/40 text-danger',
                      )}
                    >
                      {u.status}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-text-tertiary">
                    {new Date(u.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
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
