import type { OrderStatus } from '@/types/order'
import { cn } from '@/lib/cn'

const LABELS: Record<OrderStatus, string> = {
  pending_payment: 'Pending payment',
  confirmed: 'Confirmed',
  processing: 'Processing',
  packed: 'Packed',
  shipped: 'Shipped',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
  delivery_failed: 'Delivery failed',
  returned: 'Returned',
  return_requested: 'Return requested',
  return_approved: 'Return approved',
  return_rejected: 'Return rejected',
  refunded: 'Refunded',
  failed: 'Payment failed',
  cancelled: 'Cancelled',
}

const TONES: Record<OrderStatus, string> = {
  pending_payment: 'text-text-tertiary border-border-strong',
  confirmed: 'text-info border-info/40',
  processing: 'text-info border-info/40',
  packed: 'text-info border-info/40',
  shipped: 'text-info border-info/40',
  out_for_delivery: 'text-warning border-warning/40',
  delivered: 'text-success border-success/40',
  delivery_failed: 'text-danger border-danger/40',
  returned: 'text-text-tertiary border-border-strong',
  return_requested: 'text-warning border-warning/40',
  return_approved: 'text-info border-info/40',
  return_rejected: 'text-danger border-danger/40',
  refunded: 'text-text-tertiary border-border-strong',
  failed: 'text-danger border-danger/40',
  cancelled: 'text-text-tertiary border-border-strong',
}

export function OrderStatusBadge({ status }: { status: OrderStatus }) {
  return (
    <span className={cn('rounded-full border px-2 py-0.5 text-xs font-medium', TONES[status])}>
      {LABELS[status]}
    </span>
  )
}
