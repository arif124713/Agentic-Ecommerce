import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getProduct } from '@/services/catalog'
import { formatDiscount, formatMoney } from '@/lib/money'
import { RatingStars } from '@/components/product/RatingStars'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/feedback/EmptyState'
import { Skeleton } from '@/components/feedback/Skeleton'
import { getApiErrorMessage } from '@/services/apiClient'
import { cn } from '@/lib/cn'
import { useAddToCart } from '@/hooks/useCart'
import { useCartDrawerStore } from '@/store/cartDrawerStore'
import { useCurrentUser } from '@/hooks/useAuth'
import { useToggleWishlist, useWishlistSlugs } from '@/hooks/useWishlist'
import {
  getFrequentlyBoughtTogether,
  getRecentlyViewed,
  getSimilarProducts,
  recordProductView,
} from '@/services/discovery'
import { ProductRail } from '@/components/product/ProductRail'
import { NotifyMeForm } from '@/components/product/NotifyMeForm'
import { ReviewsSection } from '@/components/product/ReviewsSection'
import { SeoHead } from '@/components/seo/SeoHead'
import { breadcrumbListSchema, productSchema } from '@/lib/structuredData'

export function ProductPage() {
  const { productSlug } = useParams()
  const navigate = useNavigate()
  const [selectedColor, setSelectedColor] = useState<string | null>(null)
  const [selectedSize, setSelectedSize] = useState<string | null>(null)
  const addToCart = useAddToCart()
  const openCartDrawer = useCartDrawerStore((s) => s.open)
  const { data: user } = useCurrentUser()
  const wishlistSlugs = useWishlistSlugs()
  const toggleWishlist = useToggleWishlist()

  const query = useQuery({
    queryKey: ['products', 'detail', productSlug],
    queryFn: () => getProduct(productSlug!),
    enabled: Boolean(productSlug),
  })

  useEffect(() => {
    if (productSlug && user) recordProductView(productSlug).catch(() => {})
  }, [productSlug, user])

  const similarQuery = useQuery({
    queryKey: ['products', 'similar', productSlug],
    queryFn: () => getSimilarProducts(productSlug!),
    enabled: Boolean(productSlug),
    staleTime: 5 * 60 * 1000,
  })

  const frequentlyBoughtQuery = useQuery({
    queryKey: ['products', 'frequently-bought-together', productSlug],
    queryFn: () => getFrequentlyBoughtTogether(productSlug!),
    enabled: Boolean(productSlug),
    staleTime: 5 * 60 * 1000,
  })

  const recentlyViewedQuery = useQuery({
    queryKey: ['recently-viewed', productSlug],
    queryFn: () => getRecentlyViewed(),
    enabled: Boolean(user),
    staleTime: 60 * 1000,
    select: (products) => products.filter((p) => p.slug !== productSlug),
  })

  const colors = useMemo(() => {
    if (!query.data) return []
    const seen = new Map<string, string | null>()
    for (const v of query.data.variants) {
      if (v.color && !seen.has(v.color)) seen.set(v.color, v.color_hex)
    }
    return [...seen.entries()]
  }, [query.data])

  const sizes = useMemo(() => {
    if (!query.data) return []
    return [...new Set(query.data.variants.map((v) => v.size).filter(Boolean))] as string[]
  }, [query.data])

  const activeVariant = useMemo(() => {
    if (!query.data) return null
    return (
      query.data.variants.find(
        (v) => (!selectedColor || v.color === selectedColor) && (!selectedSize || v.size === selectedSize),
      ) ?? null
    )
  }, [query.data, selectedColor, selectedSize])

  if (query.isError) {
    return (
      <div className="container-page py-16">
        <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
      </div>
    )
  }

  if (query.isLoading || !query.data) {
    return (
      <div className="container-page grid grid-cols-1 gap-10 py-10 md:grid-cols-[minmax(0,420px)_1fr]">
        <Skeleton className="aspect-3/4 w-full max-w-sm" />
        <div className="space-y-4">
          <Skeleton className="h-4 w-1/4" />
          <Skeleton className="h-8 w-3/4" />
          <Skeleton className="h-6 w-1/3" />
        </div>
      </div>
    )
  }

  const product = query.data
  const hasDiscount = Number(product.discount_percent) > 0
  const primaryImage = product.images.find((i) => i.is_primary) ?? product.images[0]
  const inStock = (activeVariant?.available ?? 1) > 0
  const isWishlisted = wishlistSlugs.data?.includes(product.slug) ?? false

  return (
    <div className="container-page py-10">
      <SeoHead
        title={`${product.title} by ${product.brand.name}`}
        description={
          product.description
            ? product.description.slice(0, 155)
            : `${product.title} by ${product.brand.name} — shop at BlackCart.`
        }
        path={`/p/${product.slug}`}
        image={primaryImage?.url}
        type="product"
        structuredData={[
          productSchema(product),
          breadcrumbListSchema([
            { name: 'Home', path: '/' },
            { name: product.category.name, path: `/c/${product.category.slug}` },
            { name: product.title, path: `/p/${product.slug}` },
          ]),
        ]}
      />

      <div className="mb-6 flex items-center gap-4">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex h-9 items-center gap-1.5 rounded-(--radius-md) pr-2 text-sm text-text-secondary hover:text-text"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M15 18l-6-6 6-6" />
          </svg>
          Back
        </button>
        <nav aria-label="Breadcrumb" className="text-sm text-text-tertiary">
          <span className="capitalize">{product.category.name}</span>
        </nav>
      </div>

      <div className="grid grid-cols-1 gap-10 md:grid-cols-[minmax(0,420px)_1fr]">
        <div className="aspect-3/4 w-full max-w-sm overflow-hidden rounded-(--radius-lg) bg-surface">
          {primaryImage ? (
            <picture>
              {primaryImage.url_webp ? <source srcSet={primaryImage.url_webp} type="image/webp" /> : null}
              <img
                src={primaryImage.url}
                alt={primaryImage.alt_text ?? product.title}
                width={800}
                height={1000}
                fetchPriority="high"
                className="h-full w-full object-cover"
              />
            </picture>
          ) : null}
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
            {product.brand.name}
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-text">{product.title}</h1>

          {product.rating_avg ? (
            <a href="#reviews" className="mt-2 inline-block hover:opacity-80">
              <RatingStars value={Number(product.rating_avg)} count={product.rating_count} />
            </a>
          ) : null}

          <div className="mt-4 flex items-baseline gap-3">
            <span className="text-price text-2xl text-text">
              {formatMoney(product.price, product.currency)}
            </span>
            {hasDiscount ? (
              <>
                <span className="text-base text-text-tertiary line-through">
                  {formatMoney(product.mrp, product.currency)}
                </span>
                <span className="text-sm font-medium text-success">
                  {formatDiscount(product.discount_percent)}
                </span>
              </>
            ) : null}
          </div>

          {colors.length > 0 ? (
            <fieldset className="mt-6">
              <legend className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
                Colour {selectedColor ? `— ${selectedColor}` : ''}
              </legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {colors.map(([color, hex]) => (
                  <button
                    key={color}
                    type="button"
                    aria-pressed={selectedColor === color}
                    aria-label={color}
                    onClick={() => setSelectedColor(color === selectedColor ? null : color)}
                    className={cn(
                      'h-9 w-9 rounded-full border-2 transition-colors',
                      selectedColor === color ? 'border-white' : 'border-border-strong',
                    )}
                    style={{ backgroundColor: hex ?? undefined }}
                  />
                ))}
              </div>
            </fieldset>
          ) : null}

          {sizes.length > 0 ? (
            <fieldset className="mt-6">
              <legend className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
                Size {selectedSize ? `— ${selectedSize}` : ''}
              </legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {sizes.map((size) => (
                  <button
                    key={size}
                    type="button"
                    aria-pressed={selectedSize === size}
                    onClick={() => setSelectedSize(size === selectedSize ? null : size)}
                    className={cn(
                      'h-11 min-w-11 rounded-(--radius-md) border px-3 text-sm',
                      selectedSize === size
                        ? 'border-white text-text'
                        : 'border-border-strong text-text-secondary hover:border-text',
                    )}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </fieldset>
          ) : null}

          <div className="mt-8 flex gap-3">
            <Button
              size="lg"
              className="flex-1"
              disabled={!inStock || !activeVariant}
              loading={addToCart.isPending}
              onClick={() => {
                if (!activeVariant) return
                addToCart.mutate(
                  { variantId: activeVariant.id, quantity: 1 },
                  { onSuccess: () => openCartDrawer() },
                )
              }}
            >
              {inStock ? 'Add to cart' : 'Out of stock'}
            </Button>
            <Button
              size="lg"
              variant="secondary"
              aria-pressed={isWishlisted}
              aria-label={isWishlisted ? 'Remove from wishlist' : 'Add to wishlist'}
              onClick={() => {
                if (!user) {
                  navigate(`/auth/login?next=${encodeURIComponent(window.location.pathname)}`)
                  return
                }
                toggleWishlist.mutate(product.slug)
              }}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill={isWishlisted ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="1.75"
                aria-hidden="true"
              >
                <path d="M12 21s-6.7-4.35-9.3-8.1C1 10.1 1.6 6.7 4.6 5.2c2.3-1.15 4.7-.3 6 1.5.5.6.9 1.2 1.4 1.9.5-.7.9-1.3 1.4-1.9 1.3-1.8 3.7-2.65 6-1.5 3 1.5 3.6 4.9 1.9 7.7C18.7 16.65 12 21 12 21z" />
              </svg>
            </Button>
          </div>

          {!inStock && activeVariant ? (
            <NotifyMeForm productSlug={product.slug} variantId={activeVariant.id} />
          ) : null}

          {product.description ? (
            <div className="mt-10 border-t border-border pt-6">
              <h2 className="text-sm font-medium text-text">Description</h2>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{product.description}</p>
            </div>
          ) : null}

          {product.material ? (
            <dl className="mt-6 grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-text-tertiary">Material</dt>
                <dd className="text-text-secondary">{product.material}</dd>
              </div>
              {product.base_color ? (
                <div>
                  <dt className="text-text-tertiary">Colour</dt>
                  <dd className="text-text-secondary">{product.base_color}</dd>
                </div>
              ) : null}
            </dl>
          ) : null}
        </div>
      </div>

      <ReviewsSection productSlug={product.slug} />

      <ProductRail title="Similar products" products={similarQuery.data} loading={similarQuery.isLoading} />
      <ProductRail
        title="Frequently bought together"
        products={frequentlyBoughtQuery.data}
        loading={frequentlyBoughtQuery.isLoading}
      />
      {user ? (
        <ProductRail
          title="Recently viewed"
          products={recentlyViewedQuery.data}
          loading={recentlyViewedQuery.isLoading}
        />
      ) : null}
    </div>
  )
}
