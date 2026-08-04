import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  bulkProductAction,
  exportProductsCsv,
  importProductsCsv,
  listAdminProducts,
  listCategoryOptions,
} from '@/services/admin/catalog'
import { formatMoney } from '@/lib/money'
import { cn } from '@/lib/cn'
import { Button } from '@/components/ui/Button'
import { FormAlert } from '@/components/ui/FormAlert'
import { Skeleton } from '@/components/feedback/Skeleton'
import { EmptyState, ErrorState } from '@/components/feedback/EmptyState'
import { getApiErrorMessage } from '@/services/apiClient'
import { SeoHead } from '@/components/seo/SeoHead'
import type { ProductImportSummary } from '@/types/admin'

const PER_PAGE = 50

function ImportResultsPanel({ summary, onClose }: { summary: ProductImportSummary; onClose: () => void }) {
  const errorRows = summary.results.filter((r) => r.status === 'error')
  return (
    <div className="mt-4 rounded-(--radius-lg) border border-border p-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-text">
          Imported {summary.total} row{summary.total === 1 ? '' : 's'}: {summary.created} created,{' '}
          {summary.updated} updated, {summary.failed} failed
        </p>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Dismiss
        </Button>
      </div>
      {errorRows.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-danger">
          {errorRows.map((r) => (
            <li key={r.row}>
              Row {r.row}: {r.message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export function ProductsListPage() {
  const [searchParams] = useSearchParams()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [importSummary, setImportSummary] = useState<ProductImportSummary | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

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
    setSelected(new Set())
  }, [q, status, categoryId])

  const importMutation = useMutation({
    mutationFn: importProductsCsv,
    onSuccess: (summary) => {
      setImportSummary(summary)
      queryClient.invalidateQueries({ queryKey: ['admin', 'products'] })
      if (fileInputRef.current) fileInputRef.current.value = ''
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  const exportMutation = useMutation({
    mutationFn: exportProductsCsv,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'products_export.csv'
      a.click()
      URL.revokeObjectURL(url)
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  const bulkMutation = useMutation({
    mutationFn: (action: 'activate' | 'archive' | 'delete') => bulkProductAction(Array.from(selected), action),
    onSuccess: (result) => {
      toast.success(`${result.succeeded} of ${result.requested} product(s) ${result.action}d.`)
      queryClient.invalidateQueries({ queryKey: ['admin', 'products'] })
      setSelected(new Set())
    },
    onError: (error) => toast.error(getApiErrorMessage(error)),
  })

  const lowStockOnly = searchParams.get('lowStock') === '1'
  const products = query.data?.data ?? []

  const toggleRow = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected((prev) => (prev.size === products.length ? new Set() : new Set(products.map((p) => p.id))))
  }

  return (
    <div>
      <SeoHead
        title="Manage Products"
        description="Search, filter, and manage the BlackCart product catalogue."
        path="/admin/products"
        noindex
      />
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Products</h1>
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) importMutation.mutate(file)
            }}
          />
          <Button variant="secondary" loading={exportMutation.isPending} onClick={() => exportMutation.mutate()}>
            Export CSV
          </Button>
          <Button variant="secondary" loading={importMutation.isPending} onClick={() => fileInputRef.current?.click()}>
            Import CSV
          </Button>
          <Link
            to="/admin/products/new"
            className="flex h-10 items-center justify-center rounded-(--radius-md) bg-accent px-4 text-sm font-medium text-accent-fg hover:opacity-90"
          >
            + New product
          </Link>
        </div>
      </div>

      {importMutation.isError ? (
        <div className="mt-4">
          <FormAlert>{getApiErrorMessage(importMutation.error)}</FormAlert>
        </div>
      ) : null}
      {importSummary ? <ImportResultsPanel summary={importSummary} onClose={() => setImportSummary(null)} /> : null}

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
              {'  '.repeat(c.depth)}
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

      {selected.size > 0 ? (
        <div className="mt-4 flex items-center justify-between gap-4 rounded-(--radius-lg) border border-border-strong bg-surface-raised px-4 py-3">
          <p className="text-sm text-text">{selected.size} selected</p>
          <div className="flex gap-2">
            <Button size="sm" variant="secondary" loading={bulkMutation.isPending} onClick={() => bulkMutation.mutate('activate')}>
              Activate
            </Button>
            <Button size="sm" variant="secondary" loading={bulkMutation.isPending} onClick={() => bulkMutation.mutate('archive')}>
              Archive
            </Button>
            <Button size="sm" variant="destructive" loading={bulkMutation.isPending} onClick={() => bulkMutation.mutate('delete')}>
              Delete
            </Button>
          </div>
        </div>
      ) : null}

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
                  <th className="py-2 pr-4 font-medium">
                    <input
                      type="checkbox"
                      aria-label="Select all products on this page"
                      checked={selected.size === products.length && products.length > 0}
                      onChange={toggleAll}
                      className="h-4 w-4 rounded-sm border-border-strong accent-white"
                    />
                  </th>
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
                        <input
                          type="checkbox"
                          aria-label={`Select ${p.title}`}
                          checked={selected.has(p.id)}
                          onChange={() => toggleRow(p.id)}
                          className="h-4 w-4 rounded-sm border-border-strong accent-white"
                        />
                      </td>
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
