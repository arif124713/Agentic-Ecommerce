import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelOrder, getOrder, getTracking } from '@/services/orders'
import { formatMoney } from '@/lib/money'
import { getApiErrorMessage } from '@/services/apiClient'
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge'
import { OrderSummary } from '@/components/cart/OrderSummary'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { ErrorState } from '@/components/feedback/EmptyState'

const CANCELLABLE = new Set(['pending_payment', 'confirmed', 'processing'])
const TRACKABLE = new Set(['shipped', 'out_for_delivery'])

export function OrderDetailPage() {
  const { orderNumber } = useParams()
  const queryClient = useQueryClient()
  const [showCancelForm, setShowCancelForm] = useState(false)
  const [cancelReason, setCancelReason] = useState('')

  const order = useQuery({
    queryKey: ['orders', 'detail', orderNumber],
    queryFn: () => getOrder(orderNumber!),
    enabled: Boolean(orderNumber),
  })

  const tracking = useQuery({
    queryKey: ['orders', 'tracking', orderNumber],
    queryFn: () => getTracking(orderNumber!),
    enabled: Boolean(orderNumber) && (order.data ? order.data.status !== 'pending_payment' : false),
    refetchInterval: (query) => (TRACKABLE.has(query.state.data?.shipment_status ?? '') ? 10_000 : false),
  })

  const cancelMutation = useMutation({
    mutationFn: () => cancelOrder(orderNumber!, cancelReason || undefined),
    onSuccess: (updated) => {
      queryClient.setQueryData(['orders', 'detail', orderNumber], updated)
      queryClient.invalidateQueries({ queryKey: ['orders', 'list'] })
      setShowCancelForm(false)
    },
  })

  if (order.isError) {
    return (
      <div className="container-page py-16">
        <ErrorState message={getApiErrorMessage(order.error)} onRetry={() => order.refetch()} />
      </div>
    )
  }

  if (order.isLoading || !order.data) {
    return (
      <div className="container-page py-10">
        <Skeleton className="h-8 w-56" />
        <div className="mt-8 grid gap-10 md:grid-cols-[1fr_320px]">
          <Skeleton className="h-96 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    )
  }

  const data = order.data
  const canCancel = CANCELLABLE.has(data.status)

  return (
    <div className="container-page py-10">
      <Link to="/account/orders" className="text-sm text-text-secondary hover:text-text hover:underline">
        ← All orders
      </Link>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{data.order_number}</h1>
        <OrderStatusBadge status={data.status} />
      </div>
      <p className="mt-1 text-sm text-text-tertiary">
        Placed {new Date(data.created_at).toLocaleDateString(undefined, { month: 'long', day: 'numeric', year: 'numeric' })}
      </p>

      <div className="mt-8 grid gap-10 md:grid-cols-[1fr_320px]">
        <div className="flex flex-col gap-8">
          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Items</h2>
            <ul className="mt-4 divide-y divide-border">
              {data.items.map((item) => (
                <li key={item.variant_id} className="flex gap-4 py-4">
                  <div className="h-20 w-16 shrink-0 overflow-hidden rounded-(--radius-md) bg-surface-raised">
                    {item.image ? (
                      <img src={item.image} alt="" width={128} height={160} className="h-full w-full object-cover" />
                    ) : null}
                  </div>
                  <div className="flex-1">
                    <p className="text-xs uppercase tracking-wide text-text-tertiary">{item.brand}</p>
                    <p className="text-sm font-medium text-text">{item.title}</p>
                    <p className="mt-0.5 text-xs text-text-tertiary">
                      {[item.size, item.color].filter(Boolean).join(' · ')} · Qty {item.quantity}
                    </p>
                  </div>
                  <span className="text-price text-sm text-text">{formatMoney(item.line_total, data.currency)}</span>
                </li>
              ))}
            </ul>
          </section>

          {tracking.data && data.status !== 'pending_payment' && data.status !== 'failed' ? (
            <section>
              <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Tracking</h2>
              {tracking.data.tracking_number ? (
                <p className="mt-3 text-sm text-text-secondary">
                  {tracking.data.carrier} · <span className="font-mono text-text">{tracking.data.tracking_number}</span>
                </p>
              ) : (
                <p className="mt-3 text-sm text-text-tertiary">Your order is being prepared for shipment.</p>
              )}

              {tracking.data.events.length > 0 ? (
                <ol className="mt-4 flex flex-col gap-4 border-l border-border pl-4">
                  {tracking.data.events.map((event, i) => (
                    <li key={i} className="relative">
                      <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-text" />
                      <p className="text-sm text-text">{event.description}</p>
                      <p className="text-xs text-text-tertiary">
                        {event.location} ·{' '}
                        {new Date(event.occurred_at).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </p>
                    </li>
                  ))}
                </ol>
              ) : null}
            </section>
          ) : null}

          <section>
            <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Shipping address</h2>
            <p className="mt-3 text-sm text-text-secondary">
              {data.shipping_address.recipient_name}
              <br />
              {data.shipping_address.street_line1}
              {data.shipping_address.street_line2 ? `, ${data.shipping_address.street_line2}` : ''}
              <br />
              {data.shipping_address.city}, {data.shipping_address.division}
              {data.shipping_address.postal_code ? ` ${data.shipping_address.postal_code}` : ''}
              <br />
              {data.shipping_address.phone}
            </p>
          </section>

          {canCancel ? (
            <section>
              {showCancelForm ? (
                <div className="flex flex-col gap-3">
                  {cancelMutation.isError ? <FormAlert>{getApiErrorMessage(cancelMutation.error)}</FormAlert> : null}
                  <textarea
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Reason (optional)"
                    rows={2}
                    className="w-full rounded-(--radius-md) border border-border bg-surface-sunken p-3 text-sm text-text placeholder:text-text-tertiary"
                  />
                  <div className="flex gap-3">
                    <Button variant="destructive" loading={cancelMutation.isPending} onClick={() => cancelMutation.mutate()}>
                      Confirm cancellation
                    </Button>
                    <Button variant="ghost" onClick={() => setShowCancelForm(false)}>
                      Keep order
                    </Button>
                  </div>
                </div>
              ) : (
                <Button variant="destructive" onClick={() => setShowCancelForm(true)}>
                  Cancel order
                </Button>
              )}
            </section>
          ) : null}
        </div>

        <div className="flex flex-col gap-4">
          <OrderSummary
            currency={data.currency}
            subtotal={data.totals.subtotal}
            discountTotal={data.totals.discount_total}
            shippingFee={data.totals.shipping_fee}
            taxTotal={data.totals.tax_total}
            total={data.totals.grand_total}
          />
          {data.payment ? (
            <div className="rounded-(--radius-lg) border border-border p-5 text-sm">
              <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Payment</h2>
              <p className="mt-3 text-text-secondary">
                {data.payment.method === 'cod'
                  ? 'Cash on delivery'
                  : `${data.payment.card_brand ?? 'Card'} •••• ${data.payment.card_last4 ?? ''}`}
              </p>
              <p className="mt-1 text-text-tertiary">{data.payment_status}</p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
