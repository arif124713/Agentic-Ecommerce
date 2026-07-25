import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getAdminOrder, refundOrder, transitionOrder } from '@/services/admin/orders'
import { formatMoney } from '@/lib/money'
import { getApiErrorMessage } from '@/services/apiClient'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import { OrderSummary } from '@/components/cart/OrderSummary'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { ErrorState } from '@/components/feedback/EmptyState'
import type { OrderStatus } from '@/types/order'

const TRANSITIONS: OrderStatus[] = [
  'confirmed',
  'processing',
  'packed',
  'shipped',
  'out_for_delivery',
  'delivered',
  'delivery_failed',
  'cancelled',
  'returned',
  'refunded',
]

export function OrderDetailPage() {
  const { orderNumber } = useParams()
  const queryClient = useQueryClient()
  const [nextStatus, setNextStatus] = useState('')
  const [transitionReason, setTransitionReason] = useState('')
  const [refundAmount, setRefundAmount] = useState('')
  const [refundReason, setRefundReason] = useState('')

  const order = useQuery({
    queryKey: ['admin', 'orders', 'detail', orderNumber],
    queryFn: () => getAdminOrder(orderNumber!),
    enabled: Boolean(orderNumber),
  })

  const transitionMutation = useMutation({
    mutationFn: () => transitionOrder(orderNumber!, nextStatus, transitionReason || undefined),
    onSuccess: (updated) => {
      queryClient.setQueryData(['admin', 'orders', 'detail', orderNumber], updated)
      queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] })
      setNextStatus('')
      setTransitionReason('')
    },
  })

  const refundMutation = useMutation({
    mutationFn: () => refundOrder(orderNumber!, refundAmount, refundReason || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'orders', 'detail', orderNumber] })
      setRefundAmount('')
      setRefundReason('')
    },
  })

  if (order.isError) {
    return <ErrorState message={getApiErrorMessage(order.error)} onRetry={() => order.refetch()} />
  }
  if (order.isLoading || !order.data) {
    return <Skeleton className="h-96 w-full" />
  }

  const data = order.data

  return (
    <div>
      <Link to="/admin/orders" className="text-sm text-text-secondary hover:text-text hover:underline">
        ← All orders
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{data.order_number}</h1>
        <OrderStatusBadge status={data.status as OrderStatus} />
      </div>
      <p className="mt-1 text-sm text-text-tertiary">
        Placed {new Date(data.created_at).toLocaleString()} · {data.payment_status}
      </p>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_340px]">
        <div className="flex flex-col gap-8">
          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Items</h2>
            <ul className="mt-3 divide-y divide-border text-sm">
              {data.items.map((item) => (
                <li key={item.variant_id} className="flex justify-between py-2">
                  <span className="text-text-secondary">
                    {item.title} ({[item.size, item.color].filter(Boolean).join(' · ')}) × {item.quantity}
                  </span>
                  <span className="tabular-nums text-text">{formatMoney(item.line_total, data.currency)}</span>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Shipping address</h2>
            <p className="mt-3 text-sm text-text-secondary">
              {data.shipping_address.recipient_name}
              <br />
              {data.shipping_address.street_line1}, {data.shipping_address.city}, {data.shipping_address.division}
              <br />
              {data.shipping_address.phone}
            </p>
          </section>

          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Transition status</h2>
            {transitionMutation.isError ? (
              <div className="mt-2">
                <FormAlert>{getApiErrorMessage(transitionMutation.error)}</FormAlert>
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <select
                value={nextStatus}
                onChange={(e) => setNextStatus(e.target.value)}
                aria-label="Next order status"
                className="h-10 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
              >
                <option value="">Select next status…</option>
                {TRANSITIONS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, ' ')}
                  </option>
                ))}
              </select>
              <input
                value={transitionReason}
                onChange={(e) => setTransitionReason(e.target.value)}
                placeholder="Reason (optional)"
                className="h-10 w-56 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary"
              />
              <Button
                size="sm"
                disabled={!nextStatus}
                loading={transitionMutation.isPending}
                onClick={() => transitionMutation.mutate()}
              >
                Apply
              </Button>
            </div>
          </section>

          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Issue refund</h2>
            {refundMutation.isError ? (
              <div className="mt-2">
                <FormAlert>{getApiErrorMessage(refundMutation.error)}</FormAlert>
              </div>
            ) : null}
            {refundMutation.isSuccess ? (
              <div className="mt-2">
                <FormAlert tone="success">Refund issued.</FormAlert>
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <input
                type="number"
                step="0.01"
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                placeholder="Amount"
                className="h-10 w-32 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary"
              />
              <input
                value={refundReason}
                onChange={(e) => setRefundReason(e.target.value)}
                placeholder="Reason (optional)"
                className="h-10 w-56 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary"
              />
              <Button
                size="sm"
                variant="destructive"
                disabled={!refundAmount}
                loading={refundMutation.isPending}
                onClick={() => refundMutation.mutate()}
              >
                Issue refund
              </Button>
            </div>
          </section>
        </div>

        <OrderSummary
          currency={data.currency}
          subtotal={data.totals.subtotal}
          discountTotal={data.totals.discount_total}
          shippingFee={data.totals.shipping_fee}
          taxTotal={data.totals.tax_total}
          total={data.totals.grand_total}
        />
      </div>
    </div>
  )
}
