import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listAdminOrders } from '@/services/admin/orders'
import { formatMoney } from '@/lib/money'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import type { OrderStatus } from '@/types/order'

const STATUSES: OrderStatus[] = [
  'pending_payment',
  'confirmed',
  'processing',
  'packed',
  'shipped',
  'out_for_delivery',
  'delivered',
  'cancelled',
  'failed',
]

export function OrdersListPage() {
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')

  const query = useQuery({
    queryKey: ['admin', 'orders', q, status],
    queryFn: () => listAdminOrders({ q: q || undefined, status: status || undefined, per_page: 50 }),
  })

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Orders</h1>

      <div className="mt-6 flex gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by order number or email…"
          aria-label="Search orders by order number or email"
          className="h-11 flex-1 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
          className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
      </div>

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
          <EmptyState title="No orders found" />
        </div>
      ) : (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                <th className="py-2 pr-4 font-medium">Order</th>
                <th className="py-2 pr-4 font-medium">Customer</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Payment</th>
                <th className="py-2 pr-4 font-medium">Items</th>
                <th className="py-2 pr-4 font-medium">Total</th>
                <th className="py-2 pr-4 font-medium">Placed</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.data.map((o) => (
                <tr key={o.order_number} className="hover:bg-surface-raised">
                  <td className="py-3 pr-4">
                    <Link to={`/admin/orders/${o.order_number}`} className="font-medium text-text hover:underline">
                      {o.order_number}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-text-secondary">{o.customer_email}</td>
                  <td className="py-3 pr-4">
                    <OrderStatusBadge status={o.status as OrderStatus} />
                  </td>
                  <td className="py-3 pr-4 capitalize text-text-secondary">{o.payment_status}</td>
                  <td className="py-3 pr-4 tabular-nums text-text-secondary">{o.item_count}</td>
                  <td className="py-3 pr-4 tabular-nums text-text">{formatMoney(o.grand_total, o.currency)}</td>
                  <td className="py-3 pr-4 text-text-tertiary">
                    {new Date(o.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
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
