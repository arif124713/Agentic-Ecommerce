import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { getDashboardSummary } from '@/services/admin/dashboard'
import { formatMoney } from '@/lib/money'
import { Skeleton } from '@/components/feedback/Skeleton'
import { ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'

function StatCard({ label, value, href }: { label: string; value: string; href?: string }) {
  const content = (
    <div className="rounded-(--radius-lg) border border-border p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-text">{value}</p>
    </div>
  )
  return href ? (
    <Link to={href} className="block transition-colors hover:border-text-tertiary">
      {content}
    </Link>
  ) : (
    content
  )
}

export function DashboardPage() {
  const query = useQuery({ queryKey: ['admin', 'dashboard'], queryFn: getDashboardSummary })

  if (query.isError) {
    return <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
  }

  if (query.isLoading || !query.data) {
    return (
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    )
  }

  const d = query.data

  return (
    <div>
      <SeoHead
        title="Admin Dashboard"
        description="Overview of BlackCart orders, revenue, and inventory for store administrators."
        path="/admin"
        noindex
      />
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>

      <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Orders today" value={String(d.orders_today)} href="/admin/orders" />
        <StatCard label="Orders this week" value={String(d.orders_this_week)} href="/admin/orders" />
        <StatCard label="Revenue today" value={formatMoney(d.revenue_today, 'INR')} />
        <StatCard label="Revenue this week" value={formatMoney(d.revenue_this_week, 'INR')} />
        <StatCard label="Low stock variants" value={String(d.low_stock_count)} href="/admin/products?lowStock=1" />
        <StatCard label="Total customers" value={String(d.total_customers)} href="/admin/users" />
      </div>

      <div className="mt-8 rounded-(--radius-lg) border border-border p-5">
        <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Orders by status</h2>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          {Object.entries(d.orders_by_status).map(([status, count]) => (
            <div key={status} className="flex justify-between rounded-(--radius-md) bg-surface-raised px-3 py-2">
              <dt className="capitalize text-text-secondary">{status.replace(/_/g, ' ')}</dt>
              <dd className="font-medium text-text">{count}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
