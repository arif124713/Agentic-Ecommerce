export interface AdminVariant {
  id: number
  sku: string
  size: string | null
  color: string | null
  color_hex: string | null
  mrp: string
  price: string
  stock: number
  reserved: number
  available: number
  low_stock_threshold: number
  is_active: boolean
}

export interface VariantInput {
  sku: string
  size: string | null
  color: string | null
  color_hex: string | null
  mrp: string
  price: string
  stock: number
  low_stock_threshold: number
  is_active: boolean
}

export interface AdminProductListItem {
  id: number
  slug: string
  title: string
  brand: string
  category: string
  price: string
  mrp: string
  status: string
  stock_total: number
  thumbnail_url: string | null
  is_deleted: boolean
}

export interface AdminProductListMeta {
  page: number
  per_page: number
  total: number
  total_pages: number
  has_next: boolean
}

export interface AdminProductListResponse {
  data: AdminProductListItem[]
  meta: AdminProductListMeta
}

export interface AdminProductDetail {
  id: number
  slug: string
  title: string
  subtitle: string | null
  description: string | null
  brand_id: number
  category_id: number
  gender: string | null
  material: string | null
  base_color: string | null
  currency: string
  mrp: string
  price: string
  status: string
  is_deleted: boolean
  is_featured: boolean
  is_trending: boolean
  is_new_arrival: boolean
  thumbnail_url: string | null
  seo_title: string | null
  seo_description: string | null
  variants: AdminVariant[]
}

export type ProductInput = Omit<AdminProductDetail, 'id' | 'slug' | 'variants' | 'is_deleted'>

export interface LowStockVariant {
  variant_id: number
  sku: string
  product_title: string
  product_slug: string
  size: string | null
  color: string | null
  available: number
  low_stock_threshold: number
}

export interface BrandOption {
  id: number
  name: string
}

export interface CategoryOption {
  id: number
  name: string
  path: string
  depth: number
}

export interface AdminOrderListItem {
  order_number: string
  customer_email: string
  status: string
  payment_status: string
  currency: string
  grand_total: string
  item_count: number
  created_at: string
}

export interface AdminUserListItem {
  public_id: string
  first_name: string
  last_name: string | null
  email: string
  status: string
  roles: string[]
  created_at: string
}

export interface AdminUserDetail extends AdminUserListItem {
  email_verified_at: string | null
  last_login_at: string | null
  mfa_enabled: boolean
}

export interface Coupon {
  id: number
  code: string
  description: string | null
  discount_type: 'percent' | 'fixed' | 'free_shipping'
  discount_value: string
  max_discount_amount: string | null
  min_order_amount: string | null
  usage_limit_total: number | null
  usage_limit_per_user: number | null
  used_count: number
  stackable: boolean
  starts_at: string | null
  expires_at: string | null
  is_active: boolean
}

export type CouponInput = Omit<Coupon, 'id' | 'used_count'>

export interface DashboardSummary {
  orders_today: number
  orders_this_week: number
  revenue_today: string
  revenue_this_week: string
  orders_by_status: Record<string, number>
  low_stock_count: number
  total_customers: number
}

export const ROLE_CODES = ['customer', 'support', 'catalog_manager', 'ops_manager', 'admin', 'super_admin'] as const
