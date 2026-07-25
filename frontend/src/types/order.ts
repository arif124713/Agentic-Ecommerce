export interface OrderLine {
  variant_id: number
  sku: string
  title: string
  brand: string | null
  image: string | null
  size: string | null
  color: string | null
  unit_price: string
  quantity: number
  line_total: string
}

export interface OrderTotals {
  subtotal: string
  discount_total: string
  shipping_fee: string
  tax_total: string
  grand_total: string
}

export interface CheckoutPreview {
  items: OrderLine[]
  totals: OrderTotals
  promised_delivery_from: string
  promised_delivery_to: string
}

export interface Payment {
  method: string
  status: 'succeeded' | 'failed'
  card_last4: string | null
  card_brand: string | null
  transaction_id: string
  failure_code: string | null
  failure_message: string | null
}

export type OrderStatus =
  | 'pending_payment'
  | 'confirmed'
  | 'processing'
  | 'packed'
  | 'shipped'
  | 'out_for_delivery'
  | 'delivered'
  | 'delivery_failed'
  | 'returned'
  | 'return_requested'
  | 'return_approved'
  | 'return_rejected'
  | 'refunded'
  | 'failed'
  | 'cancelled'

export interface OrderSummary {
  order_number: string
  status: OrderStatus
  payment_status: string
  currency: string
  grand_total: string
  item_count: number
  thumbnail_url: string | null
  created_at: string
}

export interface OrderDetail {
  order_number: string
  status: OrderStatus
  payment_status: string
  fulfilment_status: string
  currency: string
  items: OrderLine[]
  totals: OrderTotals
  shipping_address: Record<string, string | null>
  billing_address: Record<string, string | null>
  customer_note: string | null
  payment: Payment | null
  promised_delivery_from: string | null
  promised_delivery_to: string | null
  delivered_at: string | null
  cancelled_at: string | null
  created_at: string
}

export interface ShipmentEvent {
  status: string
  location: string | null
  description: string | null
  occurred_at: string
}

export interface Tracking {
  order_number: string
  tracking_number: string | null
  carrier: string | null
  shipment_status: string | null
  estimated_delivery_at: string | null
  delivered_at: string | null
  events: ShipmentEvent[]
}
