import { useState } from 'react'
import { Link } from 'react-router'
import type { ChatProduct } from '@/types/chat'
import { formatMoney } from '@/lib/money'
import { RatingStars } from '@/components/product/RatingStars'
import { useAddToCart } from '@/hooks/useCart'
import { useCartDrawerStore } from '@/store/cartDrawerStore'
import { cn } from '@/lib/cn'

interface ChatProductCardProps {
  product: ChatProduct
}

// chat_spec.md §8.1: "if the product has >1 size, opens an inline size picker before adding.
// Never silently picks a size." catalog-mcp's card already carries the full variant list (see
// backend/app/mcp/catalog.py's _product_card), so — unlike the storefront's own ProductCard —
// this never needs a second fetch just to show sizes.
export function ChatProductCard({ product }: ChatProductCardProps) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const addToCart = useAddToCart()
  const openCartDrawer = useCartDrawerStore((s) => s.open)
  const hasDiscount = product.compare_at_price != null && product.compare_at_price > product.price
  const inStockVariants = product.variants.filter((v) => v.in_stock)
  const sizes = [...new Set(inStockVariants.map((v) => v.size).filter(Boolean))] as string[]

  const addVariant = (variantId: number) => {
    addToCart.mutate({ variantId, quantity: 1 }, { onSuccess: () => openCartDrawer() })
    setPickerOpen(false)
  }

  const handleAddClick = () => {
    if (sizes.length <= 1) {
      const variant = inStockVariants[0] ?? product.variants[0]
      if (variant) addVariant(variant.variant_id)
      return
    }
    setPickerOpen((v) => !v)
  }

  return (
    <div className="w-40 shrink-0 snap-start sm:w-44">
      <Link to={product.product_url} target="_blank" rel="noopener" className="block">
        <div className="aspect-4/5 overflow-hidden rounded-(--radius) bg-surface-raised">
          {product.image_url ? (
            <img src={product.image_url} alt={product.title} loading="lazy" className="h-full w-full object-cover" />
          ) : null}
        </div>
      </Link>
      <div className="mt-2 space-y-1">
        <Link to={product.product_url} target="_blank" rel="noopener" className="line-clamp-2 text-xs text-text hover:underline">
          {product.title}
        </Link>
        <div className="flex items-baseline gap-1.5">
          <span className="text-sm font-medium text-text">{formatMoney(product.price, product.currency)}</span>
          {hasDiscount ? (
            <span className="text-xs text-text-tertiary line-through">
              {formatMoney(product.compare_at_price!, product.currency)}
            </span>
          ) : null}
        </div>
        {product.rating ? <RatingStars value={product.rating} count={product.review_count} /> : null}
        {product.reason ? <p className="text-xs text-text-secondary">{product.reason}</p> : null}
      </div>

      {pickerOpen ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {product.variants
            .filter((v) => v.size)
            .map((v) => (
              <button
                key={v.variant_id}
                type="button"
                disabled={!v.in_stock}
                onClick={() => addVariant(v.variant_id)}
                className={cn(
                  'rounded-(--radius-sm) border border-border px-2 py-1 text-xs',
                  v.in_stock ? 'text-text hover:border-border-strong' : 'cursor-not-allowed text-text-disabled line-through',
                )}
              >
                {v.size}
              </button>
            ))}
        </div>
      ) : (
        <div className="mt-2 flex gap-1.5">
          {product.out_of_stock || !product.in_stock ? (
            <button
              type="button"
              className="flex-1 rounded-(--radius-sm) border border-border py-1.5 text-xs text-text-secondary hover:border-border-strong"
            >
              Notify Me
            </button>
          ) : (
            <button
              type="button"
              onClick={handleAddClick}
              disabled={addToCart.isPending}
              className="flex-1 rounded-(--radius-sm) bg-accent py-1.5 text-xs font-medium text-accent-fg disabled:opacity-60"
            >
              Add
            </button>
          )}
          <Link
            to={product.product_url}
            target="_blank"
            rel="noopener"
            className="rounded-(--radius-sm) border border-border px-2 py-1.5 text-xs text-text-secondary hover:border-border-strong"
          >
            View
          </Link>
        </div>
      )}
    </div>
  )
}
