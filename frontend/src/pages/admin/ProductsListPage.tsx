import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { listAdminProducts, listCategoryOptions } from '@/services/admin/catalog'
import { formatMoney } from '@/lib/money'
import { cn } from '@/lib/cn'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'

const PER_PAGE = 50

export function ProductsListPage() {
  const [searchParams] = useSearchParams()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [page, setPage] = useState(1)

  const categoriesQuery = useQuery({
    queryKey: ['admin', 'catalog-options', 'categories'],
    queryFn: listCategoryOptions,
    staleTime: 60 * 60 * 1000,
  })

  const query = useQuery({
    queryKey: ['admin', 'products', q, status, categoryId, page],
    queryFn: () =>
      listAdminProducts({
        q: q || undefined,
        status: status || undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        page,
        per_page: PER_PAGE,
      }),
  })

  useEffect(() => {
    setPage(1)
  }, [q, status, categoryId])

  const lowStockOnly = searchParams.get('lowStock') === '1'
  const products = query.data?.data ?? []

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
        <Link
          to="/admin/products/new"
          className="flex h-10 items-center justify-center rounded-(--radius-md) bg-accent px-4 text-sm font-medium text-accent-fg hover:opacity-90"
        >
          + New product
        </Link>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by title or slug…"
          aria-label="Search products by title or slug"
          className="h-11 min-w-0 flex-1 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
        />
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          aria-label="Filter by category"
          className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
        >
          <option value="">All categories</option>
          {(categoriesQuery.data ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {'  '.repeat(c.depth)}
              {c.name}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
          className="h-11 rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {query.isError ? (
        <div className="mt-8">
          <ErrorState message={getApiErrorMessage(query.error)} onRetry={() => query.refetch()} />
        </div>
      ) : query.isLoading || !query.data ? (
        <div className="mt-6 space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : products.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No products found" />
        </div>
      ) : (
        <>
          <p className="mt-4 text-sm text-text-tertiary">
            {query.data.meta.total.toLocaleString()} product{query.data.meta.total === 1 ? '' : 's'}
          </p>

          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wide text-text-tertiary">
                  <th className="py-2 pr-4 font-medium">Product</th>
                  <th className="py-2 pr-4 font-medium">Brand</th>
                  <th className="py-2 pr-4 font-medium">Category</th>
                  <th className="py-2 pr-4 font-medium">Price</th>
                  <th className="py-2 pr-4 font-medium">Stock</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {products
                  .filter((p) => !lowStockOnly || p.stock_total <= 20)
                  .map((p) => (
                    <tr key={p.id} className={cn('hover:bg-surface-raised', p.is_deleted && 'opacity-50')}>
                      <td className="py-3 pr-4">
                        <Link to={`/admin/products/${p.id}`} className="flex items-center gap-3">
                          <div className="h-12 w-10 shrink-0 overflow-hidden rounded-(--radius-sm) bg-surface-raised">
                            {p.thumbnail_url ? (
                              <img src={p.thumbnail_url} alt="" width={80} height={96} className="h-full w-full object-cover" />
                            ) : null}
                          </div>
                          <span className="font-medium text-text hover:underline">{p.title}</span>
                        </Link>
                      </td>
                      <td className="py-3 pr-4 text-text-secondary">{p.brand}</td>
                      <td className="py-3 pr-4 text-text-secondary">{p.category}</td>
                      <td className="py-3 pr-4 tabular-nums text-text">{formatMoney(p.price, 'INR')}</td>
                      <td className="py-3 pr-4 tabular-nums text-text-secondary">{p.stock_total}</td>
                      <td className="py-3 pr-4">
                        {p.is_deleted ? (
                          <span className="rounded-full border border-danger/40 px-2 py-0.5 text-xs text-danger">Deleted</span>
                        ) : (
                          <span className="rounded-full border border-border-strong px-2 py-0.5 text-xs capitalize text-text-secondary">
                            {p.status}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {query.data.meta.total_pages > 1 ? (
            <nav className="mt-6 flex items-center justify-center gap-3" aria-label="Pagination">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="h-10 rounded-(--radius-md) border border-border-strong px-4 text-sm text-text disabled:opacity-40"
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
                className="h-10 rounded-(--radius-md) border border-border-strong px-4 text-sm text-text disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          ) : null}
        </>
      )}
    </div>
  )
}
