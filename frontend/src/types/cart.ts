export interface CartItemVariant {
  sku: string
  size: string | null
  color: string | null
  color_hex: string | null
}

export interface CartItemProduct {
  slug: string
  title: string
  brand: string
  thumbnail_url: string | null
}

export interface CartItem {
  id: number
  variant_id: number
  variant: CartItemVariant
  product: CartItemProduct
  quantity: number
  unit_price: string
  unit_price_snapshot: string
  price_changed: boolean
  available: number
  is_active: boolean
  line_total: string
}

export interface CartTotals {
  subtotal: string
  discount_total: string
  tax_total: string
  estimated_total: string
}

export interface Cart {
  public_id: string
  currency: string
  items: CartItem[]
  coupon_code: string | null
  coupon_error: string | null
  totals: CartTotals
}
