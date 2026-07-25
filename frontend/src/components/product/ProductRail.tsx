import type { ProductCard as ProductCardType } from '@/types/catalog'
import { ProductCard } from './ProductCard'
import { Skeleton } from '@/components/feedback/Skeleton'

interface ProductRailProps {
  title: string
  products: ProductCardType[] | undefined
  loading: boolean
}

export function ProductRail({ title, products, loading }: ProductRailProps) {
  if (!loading && (!products || products.length === 0)) return null

  return (
    <section className="border-t border-border py-10">
      <h2 className="mb-5 text-lg font-semibold text-text">{title}</h2>
      <div className="flex gap-4 overflow-x-auto pb-2" style={{ scrollbarWidth: 'thin' }}>
        {loading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="w-44 shrink-0 sm:w-52">
                <Skeleton className="aspect-3/4 w-full" />
              </div>
            ))
          : products?.map((product) => (
              <div key={product.slug} className="w-44 shrink-0 sm:w-52">
                <ProductCard product={product} />
              </div>
            ))}
      </div>
    </section>
  )
}
