import type { ProductCard } from './catalog'

export interface WishlistItem {
  item_id: number
  product: ProductCard
}

export interface Wishlist {
  items: WishlistItem[]
}
