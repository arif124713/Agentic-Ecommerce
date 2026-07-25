import type { ReactNode } from 'react'
import { formatMoney } from '@/lib/money'

interface SummaryRow {
  label: string
  value: string
  muted?: boolean
}

interface OrderSummaryProps {
  currency: string
  subtotal: string
  discountTotal?: string
  shippingFee?: string
  taxTotal: string
  total: string
  totalLabel?: string
  children?: ReactNode
}

export function OrderSummary({
  currency,
  subtotal,
  discountTotal,
  shippingFee,
  taxTotal,
  total,
  totalLabel = 'Total',
  children,
}: OrderSummaryProps) {
  const rows: SummaryRow[] = [{ label: 'Subtotal', value: formatMoney(subtotal, currency) }]
  if (discountTotal && Number(discountTotal) > 0) {
    rows.push({ label: 'Discount', value: `−${formatMoney(discountTotal, currency)}` })
  }
  if (shippingFee !== undefined) {
    rows.push({
      label: 'Shipping',
      value: Number(shippingFee) === 0 ? 'Free' : formatMoney(shippingFee, currency),
    })
  } else {
    rows.push({ label: 'Shipping', value: 'Calculated at checkout', muted: true })
  }
  rows.push({ label: 'Tax', value: formatMoney(taxTotal, currency) })

  return (
    <div className="rounded-(--radius-lg) border border-border p-5">
      <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Order summary</h2>
      <dl className="mt-4 flex flex-col gap-2.5 text-sm">
        {rows.map((row) => (
          <div key={row.label} className="flex justify-between">
            <dt className="text-text-secondary">{row.label}</dt>
            <dd className={row.muted ? 'text-text-tertiary' : 'text-text'}>{row.value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex justify-between border-t border-border pt-4">
        <span className="text-sm font-medium text-text">{totalLabel}</span>
        <span className="text-price text-text">{formatMoney(total, currency)}</span>
      </div>
      {children ? <div className="mt-5">{children}</div> : null}
    </div>
  )
}
