import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listCoupons } from '@/services/admin/coupons'
import { formatMoney } from '@/lib/money'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { cn } from '@/lib/cn'
import { SeoHead } from '@/components/seo/SeoHead'

export function CouponsListPage() {
  const query = useQuery({ queryKey: ['admin', 'coupons'], queryFn: listCoupons })

  return (
    <div>
      <SeoHead
        title="Manage Coupons"
        description="Create and manage discount coupons for the BlackCart storefront."
        path="/admin/coupons"
        noindex
      />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Coupons</h1>
        <Link
          to="/admin/coupons/new"
          className="flex h-10 items-center justify-center rounded-(--radius-md) bg-accent px-4 text-sm font-medium text-accent-fg hover:opacity-90"
        >
          + New coupon
        </Link>
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
          <EmptyState title="No coupons yet" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">Code</th>
                <th className="py-2 pr-4 font-medium">Discount</th>
                <th className="py-2 pr-4 font-medium">Min order</th>
                <th className="py-2 pr-4 font-medium">Used</th>
                <th className="py-2 pr-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((c) => (
                <tr key={c.id} className="hover:bg-surface-raised">
                  <td className="py-3 pr-4">
                    <Link to={`/admin/coupons/${c.id}`} className="font-medium text-text hover:underline">
                      {c.code}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">
                    {c.discount_type === 'percent'
                      ? `${c.discount_value}%`
                      : c.discount_type === 'fixed'
                        ? formatMoney(c.discount_value, 'INR')
                        : 'Free shipping'}
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">
                    {c.min_order_amount ? formatMoney(c.min_order_amount, 'INR') : '—'}
                  </td>
                  <td className="py-3 pr-4 tabular-nums text-text-secondary">
                    {c.used_count}
                    {c.usage_limit_total ? ` / ${c.usage_limit_total}` : ''}
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className={cn(
                        'rounded-full border px-2 py-0.5 text-xs',
                        c.is_active ? 'border-border-strong text-text-secondary' : 'border-danger/40 text-danger',
                      )}
                    >
                      {c.is_active ? 'Active' : 'Inactive'}
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
