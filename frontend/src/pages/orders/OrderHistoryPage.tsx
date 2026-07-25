import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listOrders } from '@/services/orders'
import { formatMoney } from '@/lib/money'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'

export function OrderHistoryPage() {
  const query = useQuery({ queryKey: ['orders', 'list'], queryFn: listOrders })

  if (query.isError) {
    return (
      <div className="container-page py-16">
        <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
      </div>
    )
  }

  if (query.isLoading || !query.data) {
    return (
      <div className="container-page py-10">
        <Skeleton className="h-8 w-40" />
        <div className="mt-8 space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    )
  }

  if (query.data.length === 0) {
    return (
      <div className="container-page py-16">
        <EmptyState
          title="No orders yet"
          description="Your order history will show up here once you place an order."
          action={
            <Link
              to="/"
              className="mt-2 inline-flex h-11 items-center justify-center rounded-(--radius-md) bg-accent px-5 text-sm font-medium text-accent-fg hover:opacity-90"
            >
              Start shopping
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="container-page py-10">
      <h1 className="text-3xl font-semibold tracking-tight">Order history</h1>

      <ul className="mt-8 flex flex-col divide-y divide-border">
        {query.data.map((order) => (
          <li key={order.order_number}>
            <Link
              to={`/account/orders/${order.order_number}`}
              className="flex items-center gap-4 py-5 hover:bg-surface-raised"
            >
              <div className="h-16 w-14 shrink-0 overflow-hidden rounded-(--radius-md) bg-surface-raised">
                {order.thumbnail_url ? (
                  <img src={order.thumbnail_url} alt="" width={112} height={128} className="h-full w-full object-cover" />
                ) : null}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-text">{order.order_number}</p>
                  <OrderStatusBadge status={order.status} />
                </div>
                <p className="mt-0.5 text-xs text-text-tertiary">
                  {order.item_count} item{order.item_count === 1 ? '' : 's'} ·{' '}
                  {new Date(order.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
              <span className="text-price text-sm text-text">{formatMoney(order.grand_total, order.currency)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
