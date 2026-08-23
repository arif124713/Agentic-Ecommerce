import type { ChatBlock, ChatProduct } from '@/types/chat'
import { ChatProductCard } from './ChatProductCard'
import { formatMoney } from '@/lib/money'

function ContextChips({ items }: { items: { label: string; icon: string }[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item.label}
          className="rounded-(--radius-full) border border-border px-2.5 py-1 text-xs text-text-secondary"
        >
          {item.label}
        </span>
      ))}
    </div>
  )
}

function ProductGrid({ products }: { products: ChatProduct[] }) {
  return (
    <div className="-mx-1 flex snap-x gap-3 overflow-x-auto px-1 pb-1">
      {products.map((p) => (
        <ChatProductCard key={p.product_id} product={p} />
      ))}
    </div>
  )
}

function FollowupChips({ items, onPick }: { items: string[]; onPick: (text: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <button
          key={item}
          type="button"
          onClick={() => onPick(item)}
          className="rounded-(--radius-full) border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-border-strong hover:text-text"
        >
          {item}
        </button>
      ))}
    </div>
  )
}

function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function isMoneyKey(key: string): boolean {
  return /price|amount|total|revenue|value/i.test(key)
}

function OrderCard({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, v]) => v !== null && typeof v !== 'object')
  return (
    <div className="rounded-(--radius) border border-border p-3">
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        {entries.map(([key, value]) => (
          <div key={key} className="contents">
            <dt className="text-text-tertiary">{humanizeKey(key)}</dt>
            <dd className="text-text">
              {isMoneyKey(key) && typeof value === 'number' ? formatMoney(value) : String(value)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function PolicyCitation({ data }: { data: { results: { doc_title: string; heading: string; excerpt: string; policy_url: string }[] } }) {
  return (
    <div className="space-y-2">
      {data.results.map((r) => (
        <a
          key={r.policy_url}
          href={r.policy_url}
          target="_blank"
          rel="noopener"
          className="block rounded-(--radius) border border-border p-2.5 text-xs hover:border-border-strong"
        >
          <p className="font-medium text-text">
            {r.doc_title} · {r.heading}
          </p>
          <p className="mt-1 line-clamp-2 text-text-secondary">{r.excerpt}</p>
        </a>
      ))}
    </div>
  )
}

function ConfirmationPrompt({ data }: { data: Record<string, unknown> }) {
  return (
    <div className="rounded-(--radius) border border-border-strong bg-surface-raised p-3 text-xs text-text-secondary">
      <OrderCard data={data} />
    </div>
  )
}

function MetricSummary({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([, v]) => v !== null && typeof v !== 'object')
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-(--radius) border border-border p-2.5">
          <p className="text-[11px] text-text-tertiary">{humanizeKey(key)}</p>
          <p className="mt-0.5 text-sm font-medium text-text">
            {isMoneyKey(key) && typeof value === 'number' ? formatMoney(value) : String(value)}
          </p>
        </div>
      ))}
    </div>
  )
}

function DataTable({ columns, rows }: { columns: string[]; rows: Record<string, unknown>[] }) {
  return (
    <div className="overflow-x-auto rounded-(--radius) border border-border">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-border text-left text-text-tertiary">
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-2.5 py-1.5 font-medium">
                {humanizeKey(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {columns.map((c) => (
                <td key={c} className="whitespace-nowrap px-2.5 py-1.5 text-text-secondary">
                  {isMoneyKey(c) && typeof row[c] === 'number' ? formatMoney(row[c] as number) : String(row[c] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function renderChatBlock(block: ChatBlock, key: string, onFollowup: (text: string) => void) {
  switch (block.type) {
    case 'context_chips':
      return <ContextChips key={key} items={block.items} />
    case 'product_grid':
      return <ProductGrid key={key} products={block.products} />
    case 'followup_chips':
      return <FollowupChips key={key} items={block.items} onPick={onFollowup} />
    case 'order_card':
      return <OrderCard key={key} data={block.data} />
    case 'policy_citation':
      return <PolicyCitation key={key} data={block.data} />
    case 'confirmation_prompt':
      return <ConfirmationPrompt key={key} data={block.data} />
    case 'metric_summary':
      return <MetricSummary key={key} data={block.data} />
    case 'data_table':
      return <DataTable key={key} columns={block.columns} rows={block.rows} />
    case 'refusal':
      return null
    default:
      return null
  }
}
