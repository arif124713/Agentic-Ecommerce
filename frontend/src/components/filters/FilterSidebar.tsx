import type { FacetBucket } from '@/types/catalog'
import { cn } from '@/lib/cn'

interface FilterSidebarProps {
  brands: FacetBucket[]
  selectedBrands: string[]
  onToggleBrand: (brand: string) => void
  sort: string
  onSortChange: (sort: string) => void
  className?: string
}

const SORT_OPTIONS = [
  { value: '-popularity', label: 'Most popular' },
  { value: '-created_at', label: 'Newest' },
  { value: 'price', label: 'Price: low to high' },
  { value: '-price', label: 'Price: high to low' },
  { value: '-rating', label: 'Top rated' },
]

export function FilterSidebar({
  brands,
  selectedBrands,
  onToggleBrand,
  sort,
  onSortChange,
  className,
}: FilterSidebarProps) {
  return (
    <aside className={cn('space-y-8', className)}>
      <div>
        <label htmlFor="sort" className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
          Sort by
        </label>
        <select
          id="sort"
          value={sort}
          onChange={(e) => onSortChange(e.target.value)}
          className="mt-2 h-11 w-full rounded-(--radius-md) border border-border bg-surface-sunken px-3 text-sm text-text focus-visible:ring-2 focus-visible:ring-focus-ring"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {brands.length > 0 ? (
        <div>
          <h2 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">Brand</h2>
          <ul className="mt-3 space-y-2">
            {brands.map((brand) => {
              const checked = selectedBrands.includes(brand.value.toLowerCase())
              return (
                <li key={brand.value}>
                  <label className="flex min-h-11 cursor-pointer items-center justify-between gap-2 text-sm text-text-secondary">
                    <span className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onToggleBrand(brand.value.toLowerCase())}
                        className="h-4 w-4 rounded-sm border-border-strong accent-white"
                      />
                      {brand.value}
                    </span>
                    <span className="text-text-tertiary">{brand.count}</span>
                  </label>
                </li>
              )
            })}
          </ul>
        </div>
      ) : null}
    </aside>
  )
}
