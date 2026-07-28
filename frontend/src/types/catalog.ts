export interface ProductCard {
  slug: string
  title: string
  brand: string
  thumbnail_url: string | null
  price: string
  mrp: string
  discount_percent: string
  rating_avg: string | null
  rating_count: number
  currency: string
  in_stock: boolean
}

export interface FacetBucket {
  value: string
  count: number
}

export interface CategoryFacetBucket {
  slug: string
  name: string
  count: number
  is_active: boolean
}

export interface ProductFacets {
  brands: FacetBucket[]
  categories: CategoryFacetBucket[]
  sizes: FacetBucket[]
  colors: FacetBucket[]
  price_range: { min: string; max: string } | null
}

export interface ProductListMeta {
  page: number
  per_page: number
  total: number
  total_pages: number
  has_next: boolean
  search_fallback: boolean
  request_id?: string
  timestamp?: string
}

export interface ProductListResponse {
  data: ProductCard[]
  meta: ProductListMeta
  facets: ProductFacets
}

export interface ProductVariant {
  id: number
  sku: string
  size: string | null
  color: string | null
  color_hex: string | null
  price: string
  mrp: string
  available: number
  is_active: boolean
}

export interface ProductImage {
  url: string
  url_webp: string | null
  blurhash: string | null
  alt_text: string | null
  is_primary: boolean
}

export interface ProductDetail {
  slug: string
  title: string
  subtitle: string | null
  description: string | null
  brand: { name: string; slug: string; logo_url: string | null }
  category: { name: string; slug: string; path: string; depth: number }
  gender: string | null
  material: string | null
  base_color: string | null
  currency: string
  price: string
  mrp: string
  discount_percent: string
  rating_avg: string | null
  rating_count: number
  review_count: number
  images: ProductImage[]
  variants: ProductVariant[]
}

export interface Category {
  name: string
  slug: string
  path: string
  depth: number
  image_url: string | null
  icon: string | null
}

export interface Brand {
  name: string
  slug: string
  logo_url: string | null
}

export interface Envelope<T> {
  data: T
  meta: { request_id: string; timestamp: string }
}
