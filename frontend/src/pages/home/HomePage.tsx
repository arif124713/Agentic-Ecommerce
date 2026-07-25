import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listCategories, listProducts } from '@/services/catalog'
import { ProductGrid } from '@/components/product/ProductGrid'
import { ErrorState } from '@/components/feedback/EmptyState'
import { Button } from '@/components/ui/Button'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'
import { organizationAndWebsiteSchema } from '@/lib/structuredData'

export function HomePage() {
  const categories = useQuery({
    queryKey: ['categories'],
    queryFn: listCategories,
    staleTime: 60 * 60 * 1000,
  })
  const topCategories = (categories.data ?? []).filter((c) => c.depth === 0)
  const primaryCategory = topCategories[0]

  const trending = useQuery({
    queryKey: ['products', 'list', { sort: '-popularity', per_page: 12 }],
    queryFn: () => listProducts({ sort: '-popularity', per_page: 12 }),
  })

  return (
    <div>
      <SeoHead
        title="BlackCart — Fashion that speaks in black and white"
        description="Curated apparel and footwear from brands you trust. Shop men's and unisex fashion with fast delivery and easy returns."
        path="/"
        structuredData={organizationAndWebsiteSchema()}
      />

      <section className="border-b border-border">
        <div className="container-page flex min-h-[60vh] flex-col items-start justify-center gap-6 py-20">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-text-tertiary">
            New season
          </p>
          <h1 className="text-display max-w-2xl text-text">
            Fashion that speaks in black and white.
          </h1>
          <p className="max-w-lg text-lg leading-relaxed text-text-secondary">
            Curated apparel and footwear from brands you trust. No noise, just the product.
          </p>
          {topCategories.length > 0 ? (
            <div className="flex flex-wrap gap-3">
              {topCategories.slice(0, 2).map((c, i) => (
                <Link key={c.slug} to={`/c/${c.slug}`}>
                  <Button size="lg" variant={i === 0 ? 'primary' : 'secondary'}>
                    Shop {c.name.toLowerCase()}
                  </Button>
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="container-page py-16">
        <div className="mb-8 flex items-end justify-between">
          <h2 className="text-2xl font-semibold text-text">Trending now</h2>
          {primaryCategory ? (
            <Link to={`/c/${primaryCategory.slug}`} className="text-sm text-text-secondary hover:text-text">
              View all
            </Link>
          ) : null}
        </div>

        {trending.isError ? (
          <ErrorState
            message={getApiErrorMessage(trending.error)}
            onRetry={() => trending.refetch()}
          />
        ) : (
          <ProductGrid products={trending.data?.data ?? []} loading={trending.isLoading} />
        )}
      </section>
    </div>
  )
}
