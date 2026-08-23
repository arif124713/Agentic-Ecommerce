// Mirrors backend/app/schemas/chat.py's ChatResponseOut and chat_spec.md §6's block types.
// Block shapes are typed permissively (`data: unknown` etc.) rather than exhaustively — the
// backend agents build them from real tool JSON whose exact shape varies per tool, and the
// renderer components below narrow what they actually read from each.

export type ChatAgent = 'stylist' | 'support' | 'insights'

export interface ChatToolTrace {
  server: string
  tool: string
  ms: number
  ok: boolean
  error: string | null
  returned: number | null
}

export interface ChatProductVariant {
  variant_id: number
  size: string | null
  color: string | null
  in_stock: boolean
}

export interface ChatProduct {
  product_id: string
  sku: string | null
  title: string
  brand: string
  category: string
  color: string | null
  fabric: string | null
  price: number
  compare_at_price: number | null
  currency: string
  image_url: string | null
  product_url: string
  rating: number | null
  review_count: number
  in_stock: boolean
  available_sizes: string[]
  stock_level: number
  default_variant_id: number | null
  variants: ChatProductVariant[]
  reason: string
  actions: string[]
  out_of_stock?: boolean
}

export interface ContextChipsBlock {
  type: 'context_chips'
  items: { label: string; icon: string }[]
}

export interface ProductGridBlock {
  type: 'product_grid'
  products: ChatProduct[]
}

export interface FollowupChipsBlock {
  type: 'followup_chips'
  items: string[]
}

export interface OrderCardBlock {
  type: 'order_card'
  source_tool: string
  data: Record<string, unknown>
}

export interface PolicyCitationBlock {
  type: 'policy_citation'
  source_tool: string
  data: { count: number; results: { doc_title: string; heading: string; excerpt: string; policy_url: string }[] }
}

export interface ConfirmationPromptBlock {
  type: 'confirmation_prompt'
  source_tool: string
  data: Record<string, unknown>
}

export interface MetricSummaryBlock {
  type: 'metric_summary'
  source_tool: string
  data: Record<string, unknown>
}

export interface DataTableBlock {
  type: 'data_table'
  source_tool: string
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface RefusalMarker {
  type: 'refusal'
  intent: string
}

export type ChatBlock =
  | ContextChipsBlock
  | ProductGridBlock
  | FollowupChipsBlock
  | OrderCardBlock
  | PolicyCitationBlock
  | ConfirmationPromptBlock
  | MetricSummaryBlock
  | DataTableBlock
  | RefusalMarker

export interface ChatSession {
  session_id: string
  agent: ChatAgent
  expires_at: string
}

export interface ChatResponse {
  message_id: string
  session_id: string
  agent: ChatAgent
  role: 'assistant'
  content: string
  blocks: ChatBlock[]
  tool_trace: ChatToolTrace[]
  relaxation_applied: string[]
  created_at: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  blocks: ChatBlock[]
  pending?: boolean
}
