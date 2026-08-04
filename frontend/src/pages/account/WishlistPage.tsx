import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getWishlist } from '@/services/discovery'
import { ProductGrid } from '@/components/product/ProductGrid'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { Button } from '@/components/ui/Button'
import { SeoHead } from '@/components/seo/SeoHead'

export function WishlistPage() {
  const query = useQuery({
    queryKey: ['wishlist'],
    queryFn: getWishlist,
  })

  return (
    <div className="container-page py-10">
      <SeoHead
        title="Wishlist"
        description="View and manage the products you've saved to your BlackCart wishlist."
        path="/account/wishlist"
        noindex
      />
      <h1 className="text-3xl font-semibold tracking-tight">Wishlist</h1>

      <div className="mt-8">
        {query.isError ? (
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        ) : query.data && query.data.items.length === 0 ? (
          <EmptyState
            title="Your wishlist is empty"
            description="Tap the heart icon on any product to save it here for later."
            action={
              <Link to="/">
                <Button variant="secondary">Continue shopping</Button>
              </Link>
            }
          />
        ) : (
          <ProductGrid products={query.data?.items.map((i) => i.product) ?? []} loading={query.isLoading} />
        )}
      </div>
    </div>
  )
}
