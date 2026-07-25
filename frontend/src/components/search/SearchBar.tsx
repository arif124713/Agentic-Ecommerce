import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { suggestSearch } from '@/services/search'
import { formatMoney } from '@/lib/money'
import { cn } from '@/lib/cn'

type SuggestRow =
  | { kind: 'product'; slug: string; title: string; thumbnail_url: string | null; price: string; currency: string }
  | { kind: 'brand'; slug: string; name: string }
  | { kind: 'category'; slug: string; name: string }
  | { kind: 'query'; value: string }

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true" className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  )
}

export function SearchBar() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query.trim()), 200)
    return () => clearTimeout(id)
  }, [query])

  useEffect(() => setActiveIndex(-1), [debounced])

  const suggestQuery = useQuery({
    queryKey: ['search', 'suggest', debounced],
    queryFn: () => suggestSearch(debounced),
    enabled: open && debounced.length >= 2,
    staleTime: 60 * 1000,
  })

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  const rows: SuggestRow[] = useMemo(() => {
    const data = suggestQuery.data
    if (!data) return []
    return [
      ...data.products.map((p) => ({ kind: 'product' as const, ...p })),
      ...data.brands.map((b) => ({ kind: 'brand' as const, ...b })),
      ...data.categories.map((c) => ({ kind: 'category' as const, ...c })),
      ...data.popular_queries.map((value) => ({ kind: 'query' as const, value })),
    ]
  }, [suggestQuery.data])

  function close() {
    setOpen(false)
    setQuery('')
  }

  function submit(q: string) {
    const trimmed = q.trim()
    if (!trimmed) return
    close()
    navigate(`/search?q=${encodeURIComponent(trimmed)}`)
  }

  function go(row: SuggestRow) {
    close()
    if (row.kind === 'product') navigate(`/p/${row.slug}`)
    else if (row.kind === 'brand') navigate(`/search?q=${encodeURIComponent(row.name)}`)
    else if (row.kind === 'category') navigate(`/c/${row.slug}`)
    else navigate(`/search?q=${encodeURIComponent(row.value)}`)
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      setOpen(false)
      return
    }
    if (e.key === 'ArrowDown' && rows.length > 0) {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, rows.length - 1))
    } else if (e.key === 'ArrowUp' && rows.length > 0) {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIndex >= 0 && rows[activeIndex]) go(rows[activeIndex])
      else submit(query)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Search"
          className="flex h-11 w-11 items-center justify-center rounded-(--radius-md) hover:bg-surface-raised"
        >
          <SearchIcon />
        </button>
      ) : (
        <div className="fixed inset-x-0 top-16 z-50 border-b border-border bg-bg px-4 py-3 shadow-lg sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-96 sm:rounded-(--radius-lg) sm:border sm:px-3 sm:shadow-xl">
          <form
            role="search"
            onSubmit={(e) => {
              e.preventDefault()
              if (activeIndex >= 0 && rows[activeIndex]) go(rows[activeIndex])
              else submit(query)
            }}
            className="flex items-center gap-2"
          >
            <SearchIcon className="shrink-0 text-text-tertiary" />
            <input
              ref={inputRef}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Search products, brands…"
              aria-label="Search products"
              role="combobox"
              aria-expanded={rows.length > 0}
              aria-controls="search-suggest-listbox"
              aria-activedescendant={activeIndex >= 0 ? `search-row-${activeIndex}` : undefined}
              className="h-11 flex-1 bg-transparent text-base text-text placeholder:text-text-tertiary focus:outline-none sm:text-sm"
            />
            <button
              type="button"
              onClick={close}
              aria-label="Close search"
              className="flex h-9 w-9 shrink-0 items-center justify-center text-text-tertiary hover:text-text"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </form>

          {debounced.length >= 2 ? (
            <ul
              id="search-suggest-listbox"
              role="listbox"
              aria-label="Search suggestions"
              className="mt-2 max-h-[70vh] overflow-y-auto border-t border-border pt-2"
            >
              {rows.length === 0 && !suggestQuery.isLoading ? (
                <li className="px-2 py-4 text-sm text-text-tertiary">No matches for &ldquo;{debounced}&rdquo;.</li>
              ) : (
                rows.map((row, i) => (
                  <li key={`${row.kind}-${i}`} id={`search-row-${i}`} role="option" aria-selected={i === activeIndex}>
                    <button
                      type="button"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => go(row)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-(--radius-sm) px-2 py-2.5 text-left text-sm',
                        i === activeIndex ? 'bg-surface-raised' : 'hover:bg-surface-raised',
                      )}
                    >
                      {row.kind === 'product' ? (
                        <>
                          <span className="h-10 w-8 shrink-0 overflow-hidden rounded-(--radius-sm) bg-surface">
                            {row.thumbnail_url ? (
                              <img src={row.thumbnail_url} alt="" className="h-full w-full object-cover" />
                            ) : null}
                          </span>
                          <span className="flex-1 truncate text-text">{row.title}</span>
                          <span className="shrink-0 text-text-tertiary">{formatMoney(row.price, row.currency)}</span>
                        </>
                      ) : row.kind === 'brand' ? (
                        <>
                          <span className="w-16 shrink-0 text-xs uppercase tracking-wide text-text-tertiary">Brand</span>
                          <span className="text-text">{row.name}</span>
                        </>
                      ) : row.kind === 'category' ? (
                        <>
                          <span className="w-16 shrink-0 text-xs uppercase tracking-wide text-text-tertiary">Category</span>
                          <span className="text-text">{row.name}</span>
                        </>
                      ) : (
                        <>
                          <SearchIcon className="h-4 w-4 shrink-0 text-text-tertiary" />
                          <span className="text-text-secondary">{row.value}</span>
                        </>
                      )}
                    </button>
                  </li>
                ))
              )}
            </ul>
          ) : null}
        </div>
      )}
    </div>
  )
}
