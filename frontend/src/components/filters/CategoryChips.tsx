import { Link } from 'react-router'
import type { CategoryFacetBucket } from '@/types/catalog'
import { cn } from '@/lib/cn'

interface CategoryChipsProps {
  categories: CategoryFacetBucket[]
  currentSlug?: string
}

export function CategoryChips({ categories, currentSlug }: CategoryChipsProps) {
  if (categories.length === 0) return null

  return (
    <nav aria-label="Sub-categories" className="mb-8 -mx-4 overflow-x-auto px-4 pb-1">
      <ul className="flex gap-2">
        {categories.map((c) => {
          const active = c.is_active || c.slug === currentSlug
          return (
            <li key={c.slug} className="shrink-0">
              <Link
                to={`/c/${c.slug}`}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex h-10 items-center gap-1.5 rounded-(--radius-full) border px-4 text-sm whitespace-nowrap transition-colors',
                  active
                    ? 'border-white bg-white text-black font-medium'
                    : 'border-border-strong text-text-secondary hover:border-text hover:text-text',
                )}
              >
                {c.name}
                <span className={cn('text-xs', active ? 'text-black/60' : 'text-text-tertiary')}>
                  {c.count}
                </span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
