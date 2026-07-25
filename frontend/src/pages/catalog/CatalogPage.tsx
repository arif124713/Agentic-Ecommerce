import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listProducts } from '@/services/catalog'
import { ProductGrid } from '@/components/product/ProductGrid'
import { FilterSidebar } from '@/components/filters/FilterSidebar'
import { CategoryChips } from '@/components/filters/CategoryChips'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'
import { breadcrumbListSchema, itemListSchema } from '@/lib/structuredData'

const PER_PAGE = 24

export function CatalogPage() {
  const { categorySlug } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(1)

  const sort = searchParams.get('sort') ?? '-popularity'
  const brandParam = searchParams.get('brand')
  const selectedBrands = useMemo(() => (brandParam ? brandParam.split(',') : []), [brandParam])
  const q = searchParams.get('q') ?? undefined

  useEffect(() => {
    setPage(1)
  }, [categorySlug])

  const query = useQuery({
    queryKey: ['products', 'list', { categorySlug, sort, selectedBrands, page, q }],
    queryFn: () =>
      listProducts({
        category: categorySlug,
        sort,
        brand: selectedBrands.length ? selectedBrands.join(',') : undefined,
        page,
        per_page: PER_PAGE,
        q,
      }),
  })

  function updateParams(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(next)) {
      if (value === null) params.delete(key)
      else params.set(key, value)
    }
    setSearchParams(params)
    setPage(1)
  }

  function toggleBrand(brand: string) {
    const next = selectedBrands.includes(brand)
      ? selectedBrands.filter((b) => b !== brand)
      : [...selectedBrands, brand]
    updateParams({ brand: next.length ? next.join(',') : null })
  }

  const title = q ? `Results for "${q}"` : categorySlug ? categorySlug.replace(/-/g, ' ') : 'All products'
  const canonicalPath = categorySlug ? `/c/${categorySlug}` : '/search'
  const products = query.data?.data ?? []

  return (
    <div className="container-page py-10">
      <SeoHead
        title={title}
        description={
          categorySlug
            ? `Shop ${title.toLowerCase()} at BlackCart — curated apparel and footwear, fast delivery, easy returns.`
            : `Search results for "${q}" at BlackCart.`
        }
        path={canonicalPath}
        noindex={Boolean(q)}
        structuredData={[
          breadcrumbListSchema(
            categorySlug
              ? [
                  { name: 'Home', path: '/' },
                  { name: title, path: canonicalPath },
                ]
              : [{ name: 'Home', path: '/' }],
          ),
          ...(products.length ? [itemListSchema(products)] : []),
        ]}
      />

      <header className="mb-8">
        <h1 className="text-2xl font-semibold capitalize text-text">{title}</h1>
        {query.data ? (
          <p className="mt-1 text-sm text-text-tertiary">{query.data.meta.total} products</p>
        ) : null}
      </header>

      <CategoryChips categories={query.data?.facets.categories ?? []} currentSlug={categorySlug} />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[220px_1fr]">
        <FilterSidebar
          brands={query.data?.facets.brands ?? []}
          selectedBrands={selectedBrands}
          onToggleBrand={toggleBrand}
          sort={sort}
          onSortChange={(value) => updateParams({ sort: value })}
          className="hidden lg:block"
        />

        <div>
          {query.isError ? (
            <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
          ) : query.data && query.data.data.length === 0 ? (
            <EmptyState
              title={q ? `No results for "${q}"` : 'No products found'}
              description={
                q
                  ? 'Check the spelling, try a shorter or more general term, or browse the full catalogue instead.'
                  : 'Try adjusting your filters or search for something else.'
              }
              action={
                q ? (
                  <Link
                    to="/"
                    className="mt-2 h-10 rounded-(--radius-md) border border-border-strong px-4 text-sm text-text hover:bg-surface-raised inline-flex items-center"
                  >
                    Browse all products
                  </Link>
                ) : undefined
              }
            />
          ) : (
            <>
              {q && query.data?.meta.search_fallback ? (
                <p className="mb-4 text-sm text-text-tertiary">
                  No exact matches for &ldquo;{q}&rdquo; — showing related results instead.
                </p>
              ) : null}
              <ProductGrid products={query.data?.data ?? []} loading={query.isLoading} />

              {query.data && query.data.meta.total_pages > 1 ? (
                <nav className="mt-10 flex items-center justify-center gap-2" aria-label="Pagination">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="h-11 rounded-(--radius-md) border border-border-strong px-4 text-sm text-text disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-text-tertiary">
                    Page {page} of {query.data.meta.total_pages}
                  </span>
                  <button
                    type="button"
                    disabled={!query.data.meta.has_next}
                    onClick={() => setPage((p) => p + 1)}
                    className="h-11 rounded-(--radius-md) border border-border-strong px-4 text-sm text-text disabled:opacity-40"
                  >
                    Next
                  </button>
                </nav>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
