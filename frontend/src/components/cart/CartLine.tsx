import { Link } from 'react-router'
import type { CartItem } from '@/types/cart'
import { formatMoney } from '@/lib/money'
import { cn } from '@/lib/cn'

interface CartLineProps {
  item: CartItem
  currency: string
  onUpdateQuantity: (quantity: number) => void
  onRemove: () => void
  updating?: boolean
}

export function CartLine({ item, currency, onUpdateQuantity, onRemove, updating }: CartLineProps) {
  const unavailable = !item.is_active || item.available <= 0

  return (
    <li className="flex gap-4 py-4">
      <Link
        to={`/p/${item.product.slug}`}
        className="h-24 w-20 shrink-0 overflow-hidden rounded-(--radius-md) bg-surface-raised"
      >
        {item.product.thumbnail_url ? (
          <img
            src={item.product.thumbnail_url}
            alt={item.product.title}
            width={160}
            height={192}
            className="h-full w-full object-cover"
          />
        ) : null}
      </Link>

      <div className="flex flex-1 flex-col gap-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs uppercase tracking-wide text-text-tertiary">{item.product.brand}</p>
            <Link to={`/p/${item.product.slug}`} className="text-sm font-medium text-text hover:underline">
              {item.product.title}
            </Link>
            <p className="mt-0.5 text-xs text-text-tertiary">
              {[item.variant.size, item.variant.color].filter(Boolean).join(' · ')}
            </p>
          </div>
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove item"
            className="flex h-9 w-9 shrink-0 items-center justify-center text-text-tertiary hover:text-danger"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true">
              <path d="M4 7h16M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2m2 0-1 13a2 2 0 01-2 2H8a2 2 0 01-2-2L5 7h14z" />
            </svg>
          </button>
        </div>

        {unavailable ? (
          <p className="text-xs text-danger">No longer available</p>
        ) : item.price_changed ? (
          <p className="text-xs text-warning">Price updated since you added this</p>
        ) : null}

        <div className="mt-auto flex items-center justify-between">
          <div
            className={cn(
              'flex h-9 items-center rounded-(--radius-md) border border-border-strong',
              updating && 'opacity-50',
            )}
          >
            <button
              type="button"
              disabled={updating || item.quantity <= 1}
              onClick={() => onUpdateQuantity(item.quantity - 1)}
              aria-label="Decrease quantity"
              className="flex h-9 w-9 items-center justify-center text-text disabled:opacity-30"
            >
              −
            </button>
            <span className="w-6 text-center text-sm tabular-nums">{item.quantity}</span>
            <button
              type="button"
              disabled={updating || item.quantity >= Math.min(10, item.available)}
              onClick={() => onUpdateQuantity(item.quantity + 1)}
              aria-label="Increase quantity"
              className="flex h-9 w-9 items-center justify-center text-text disabled:opacity-30"
            >
              +
            </button>
          </div>
          <span className="text-price text-sm text-text">{formatMoney(item.line_total, currency)}</span>
        </div>
      </div>
    </li>
  )
}
