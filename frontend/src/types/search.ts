export interface SuggestProduct {
  slug: string
  title: string
  thumbnail_url: string | null
  price: string
  currency: string
}

export interface SuggestBrand {
  name: string
  slug: string
}

export interface SuggestCategory {
  name: string
  slug: string
}

export interface SearchSuggestResponse {
  products: SuggestProduct[]
  brands: SuggestBrand[]
  categories: SuggestCategory[]
  popular_queries: string[]
}
