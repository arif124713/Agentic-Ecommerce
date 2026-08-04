import { Link, useNavigate } from 'react-router'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { ProductCard as ProductCardType } from '@/types/catalog'
import { formatDiscount, formatMoney } from '@/lib/money'
import { RatingStars } from './RatingStars'
import { cn } from '@/lib/cn'
import { getProduct } from '@/services/catalog'
import { useAddToCart } from '@/hooks/useCart'
import { useCartDrawerStore } from '@/store/cartDrawerStore'
import { useCurrentUser } from '@/hooks/useAuth'
import { useToggleWishlist, useWishlistSlugs } from '@/hooks/useWishlist'

interface ProductCardProps {
  product: ProductCardType
}

export function ProductCard({ product }: ProductCardProps) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const hasDiscount = Number(product.discount_percent) > 0
  const addToCart = useAddToCart()
  const openCartDrawer = useCartDrawerStore((s) => s.open)
  const autoAddedRef = useRef(false)
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const wishlistSlugs = useWishlistSlugs()
  const toggleWishlist = useToggleWishlist()
  const wishlisted = wishlistSlugs.data?.includes(product.slug) ?? false

  const detailQuery = useQuery({
    queryKey: ['products', 'detail', product.slug],
    queryFn: () => getProduct(product.slug),
    enabled: pickerOpen,
    staleTime: 5 * 60 * 1000,
  })

  const availableVariants = useMemo(
    () => (detailQuery.data?.variants ?? []).filter((v) => v.is_active && v.available > 0),
    [detailQuery.data],
  )
  const sizes = useMemo(() => [...new Set(availableVariants.map((v) => v.size).filter(Boolean))] as string[], [availableVariants])

  const addVariant = (variantId: number) => {
    addToCart.mutate({ variantId, quantity: 1 }, { onSuccess: () => openCartDrawer() })
    setPickerOpen(false)
  }

  // A single-variant (or single-size) product has nothing to choose — add it the moment the
  // detail query resolves instead of showing a one-option picker. Guarded by a ref so this only
  // ever fires once per open, not on every re-render while the mutation is in flight.
  useEffect(() => {
    if (!pickerOpen || !detailQuery.isSuccess || autoAddedRef.current) return
    if (sizes.length <= 1) {
      autoAddedRef.current = true
      if (availableVariants.length > 0) addVariant(availableVariants[0].id)
      else setPickerOpen(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickerOpen, detailQuery.isSuccess, sizes.length, availableVariants])

  const showSizeRow = pickerOpen && detailQuery.isSuccess && sizes.length > 1
  const isBusy = pickerOpen && !showSizeRow

  return (
    <div className="group relative">
      {/* Interactive controls (wishlist, size-picker, quick-add) live as siblings of the Link,
          not nested inside it — <a> containing <button> is invalid HTML5 (interactive content
          can't nest) and leaves keyboard/screen-reader activation of the inner buttons genuinely
          ambiguous. The outer `relative` wrapper above already gives the same absolute-positioning
          context, so the visual layout is unchanged. */}
      <Link
        to={`/p/${product.slug}`}
        className="block rounded-(--radius-md) outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
      >
        <div className="relative aspect-3/4 overflow-hidden rounded-(--radius-md) bg-surface">
          {product.thumbnail_url ? (
            <img
              src={product.thumbnail_url}
              alt={product.title}
              loading="lazy"
              width={800}
              height={1000}
              className="h-full w-full object-cover transition-transform duration-300 ease-(--ease-standard) group-hover:scale-105"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-text-tertiary text-sm">
              No image
            </div>
          )}

          {hasDiscount ? (
            <span className="absolute left-2 top-2 rounded-(--radius-sm) bg-accent px-2 py-1 text-xs font-semibold text-accent-fg">
              {formatDiscount(product.discount_percent)}
            </span>
          ) : null}

          {!product.in_stock ? (
            <div className="absolute inset-0 flex items-center justify-center bg-overlay">
              <span className="rounded-(--radius-sm) bg-surface px-3 py-1 text-xs font-medium text-text-secondary">
                Out of stock
              </span>
            </div>
          ) : null}
        </div>

        <div className="mt-3 space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">{product.brand}</p>
          <h3 className="line-clamp-2 text-sm text-text-secondary leading-snug min-h-10">{product.title}</h3>

          <div className="flex items-baseline gap-2 pt-1">
            <span className="text-price text-text">{formatMoney(product.price, product.currency)}</span>
            {hasDiscount ? (
              <span className="text-xs text-text-tertiary line-through">
                {formatMoney(product.mrp, product.currency)}
              </span>
            ) : null}
          </div>

          {product.rating_avg ? (
            <RatingStars value={Number(product.rating_avg)} count={product.rating_count} />
          ) : null}
        </div>
      </Link>

      <button
        type="button"
        onClick={() => {
          if (!user) {
            navigate(`/auth/login?next=${encodeURIComponent(window.location.pathname)}`)
            return
          }
          toggleWishlist.mutate(product.slug)
        }}
        aria-pressed={wishlisted}
        aria-label={wishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
        className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-full bg-surface/80 backdrop-blur-sm text-text opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill={wishlisted ? 'var(--text)' : 'none'}
          stroke="var(--text)"
          strokeWidth="1.75"
          aria-hidden="true"
        >
          <path d="M12 21s-6.7-4.35-9.3-8.1C1 10.1 1.6 6.7 4.6 5.2c2.3-1.15 4.7-.3 6 1.5.5.6.9 1.2 1.4 1.9.5-.7.9-1.3 1.4-1.9 1.3-1.8 3.7-2.65 6-1.5 3 1.5 3.6 4.9 1.9 7.7C18.7 16.65 12 21 12 21z" />
        </svg>
      </button>

      {showSizeRow ? (
        <div
          role="group"
          aria-label="Choose a size to add to cart"
          className="absolute inset-x-2 bottom-2 z-10 flex flex-wrap gap-1.5 rounded-(--radius-sm) bg-surface/95 p-2 backdrop-blur-sm"
        >
          {sizes.map((size) => (
            <button
              key={size}
              type="button"
              onClick={() => {
                const variant = availableVariants.find((v) => v.size === size)
                if (variant) addVariant(variant.id)
              }}
              className="flex h-8 min-w-8 items-center justify-center rounded-(--radius-sm) border border-border-strong px-2 text-xs text-text hover:border-text"
            >
              {size}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setPickerOpen(false)}
            aria-label="Cancel"
            className="ml-auto flex h-8 w-8 items-center justify-center text-text-tertiary hover:text-text"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={!product.in_stock}
          className={cn(
            'absolute inset-x-2 bottom-2 h-10 rounded-(--radius-sm) bg-accent text-sm font-medium text-accent-fg',
            'opacity-0 translate-y-1 transition-[opacity,transform] duration-150 ease-(--ease-standard)',
            'group-hover:opacity-100 group-hover:translate-y-0 group-focus-within:opacity-100 group-focus-within:translate-y-0 focus-visible:opacity-100',
            'disabled:opacity-0 disabled:pointer-events-none',
          )}
          onClick={() => {
            autoAddedRef.current = false
            setPickerOpen(true)
          }}
        >
          {isBusy ? 'Adding…' : 'Quick add'}
        </button>
      )}
    </div>
  )
}
