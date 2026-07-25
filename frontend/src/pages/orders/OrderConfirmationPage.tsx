import { Link, useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getOrder } from '@/services/orders'
import { formatMoney } from '@/lib/money'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/feedback/Skeleton'
import { ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'

export function OrderConfirmationPage() {
  const { orderNumber } = useParams()
  const query = useQuery({
    queryKey: ['orders', 'detail', orderNumber],
    queryFn: () => getOrder(orderNumber!),
    enabled: Boolean(orderNumber),
  })

  if (query.isLoading || !query.data) {
    return (
      <div className="container-page flex justify-center py-16">
        <div className="w-full max-w-md">
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    )
  }

  if (query.isError) {
    return (
      <div className="container-page py-16">
        <ErrorState message={getApiErrorMessage(query.error)} />
      </div>
    )
  }

  const order = query.data
  const paymentFailed = order.payment?.status === 'failed'

  if (paymentFailed) {
    return (
      <div className="container-page flex justify-center py-16">
        <div className="w-full max-w-md text-center">
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="var(--danger)"
            strokeWidth="1.5"
            className="mx-auto"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M15 9l-6 6M9 9l6 6" />
          </svg>
          <h1 className="mt-4 text-2xl font-semibold text-text">Payment failed</h1>
          <p className="mt-2 text-sm text-text-secondary">
            {order.payment?.failure_message ?? 'Your payment could not be processed.'}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              to="/checkout"
              className="flex h-11 items-center justify-center rounded-(--radius-md) bg-accent px-5 text-sm font-medium text-accent-fg hover:opacity-90"
            >
              Try again
            </Link>
            <Link
              to="/cart"
              className="flex h-11 items-center justify-center rounded-(--radius-md) border border-border-strong px-5 text-sm text-text hover:bg-surface-raised"
            >
              View cart
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="container-page flex justify-center py-16">
      <div className="w-full max-w-md text-center">
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          stroke="var(--success)"
          strokeWidth="1.5"
          className="mx-auto"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12.5l2.5 2.5L16 9" />
        </svg>
        <h1 className="mt-4 text-2xl font-semibold text-text">Order placed</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Confirmation for order <span className="font-medium text-text">{order.order_number}</span> has been sent
          to your email.
        </p>

        <div className="mt-6 rounded-(--radius-lg) border border-border p-5 text-left">
          <div className="flex justify-between text-sm">
            <span className="text-text-secondary">Total paid</span>
            <span className="text-price text-text">{formatMoney(order.totals.grand_total, order.currency)}</span>
          </div>
          {order.promised_delivery_from ? (
            <div className="mt-2 flex justify-between text-sm">
              <span className="text-text-secondary">Estimated delivery</span>
              <span className="text-text">
                {new Date(order.promised_delivery_from).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                {' – '}
                {order.promised_delivery_to
                  ? new Date(order.promised_delivery_to).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                  : ''}
              </span>
            </div>
          ) : null}
        </div>

        <div className="mt-6 flex justify-center gap-3">
          <Link to={`/account/orders/${order.order_number}`}>
            <Button>Track order</Button>
          </Link>
          <Link
            to="/"
            className="flex h-11 items-center justify-center rounded-(--radius-md) border border-border-strong px-5 text-sm text-text hover:bg-surface-raised"
          >
            Continue shopping
          </Link>
        </div>
      </div>
    </div>
  )
}
