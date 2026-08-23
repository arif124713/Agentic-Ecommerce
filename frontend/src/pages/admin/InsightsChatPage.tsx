import { useEffect, useRef, useState } from 'react'
import type { ChatBlock, ChatMessage, DataTableBlock, MetricSummaryBlock } from '@/types/chat'
import { useInsightsChat } from '@/hooks/useInsightsChat'
import { formatMoney } from '@/lib/money'

const SUGGESTED_PROMPTS = ["Yesterday's sales", "What's running low", 'Last week vs the week before', 'Top sellers this month']

function humanizeKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function isMoneyKey(key: string): boolean {
  return /price|amount|total|revenue|value/i.test(key)
}

function KpiStrip({ block }: { block: MetricSummaryBlock }) {
  const entries = Object.entries(block.data).filter(([, v]) => v !== null && typeof v !== 'object')
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-(--radius) border border-border p-4">
          <p className="text-xs text-text-tertiary">{humanizeKey(key)}</p>
          <p className="mt-1 text-xl font-semibold text-text">
            {isMoneyKey(key) && typeof value === 'number' ? formatMoney(value) : String(value)}
          </p>
        </div>
      ))}
    </div>
  )
}

function toCsv(columns: string[], rows: Record<string, unknown>[]): string {
  const escape = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const header = columns.map(escape).join(',')
  const body = rows.map((row) => columns.map((c) => escape(row[c])).join(',')).join('\n')
  return `${header}\n${body}`
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function SortableTable({ block }: { block: DataTableBlock }) {
  const [sort, setSort] = useState<{ column: string; dir: 1 | -1 } | null>(null)

  const rows = sort
    ? [...block.rows].sort((a, b) => {
        const av = a[sort.column]
        const bv = b[sort.column]
        if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * sort.dir
        return String(av ?? '').localeCompare(String(bv ?? '')) * sort.dir
      })
    : block.rows

  const toggleSort = (column: string) =>
    setSort((prev) => (prev?.column === column ? { column, dir: prev.dir === 1 ? -1 : 1 } : { column, dir: 1 }))

  return (
    <div className="space-y-2">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => downloadCsv(`${block.source_tool}.csv`, toCsv(block.columns, rows))}
          className="rounded-(--radius-sm) border border-border px-2.5 py-1 text-xs text-text-secondary hover:border-border-strong hover:text-text"
        >
          Export CSV
        </button>
      </div>
      <div className="overflow-x-auto rounded-(--radius) border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-text-tertiary">
              {block.columns.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">
                  <button type="button" onClick={() => toggleSort(c)} className="flex items-center gap-1 hover:text-text">
                    {humanizeKey(c)}
                    {sort?.column === c ? <span aria-hidden="true">{sort.dir === 1 ? '↑' : '↓'}</span> : null}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                {block.columns.map((c) => (
                  <td key={c} className="whitespace-nowrap px-3 py-2 text-text-secondary">
                    {isMoneyKey(c) && typeof row[c] === 'number' ? formatMoney(row[c] as number) : String(row[c] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function renderBlock(block: ChatBlock, key: string) {
  if (block.type === 'metric_summary') return <KpiStrip key={key} block={block} />
  if (block.type === 'data_table') return <SortableTable key={key} block={block} />
  return null
}

function InsightsMessage({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={isUser ? 'flex justify-end' : 'space-y-3'}>
      <div
        className={
          isUser
            ? 'max-w-xl rounded-(--radius) bg-accent px-3.5 py-2.5 text-sm text-accent-fg'
            : 'max-w-2xl rounded-(--radius) bg-surface-raised px-3.5 py-2.5 text-sm text-text'
        }
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
      {!isUser && message.blocks.length > 0 ? (
        <div className="space-y-3">{message.blocks.map((b, i) => renderBlock(b, `${message.id}-${i}`))}</div>
      ) : null}
    </div>
  )
}

export function InsightsChatPage() {
  const { messages, draft, setDraft, sendMessage, isSending } = useInsightsChat()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void sendMessage(draft)
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-4rem)] max-w-[900px] flex-col">
      <h1 className="text-lg font-semibold text-text">Ask BlackCart</h1>
      <div ref={scrollRef} className="mt-4 flex-1 space-y-6 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
            <p className="text-sm text-text-secondary">Ask about sales, stock, or performance in plain language.</p>
            <div className="flex flex-wrap justify-center gap-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => void sendMessage(p)}
                  className="rounded-(--radius-full) border border-border px-3.5 py-2 text-sm text-text-secondary hover:border-border-strong hover:text-text"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <InsightsMessage key={m.id} message={m} />)
        )}
      </div>
      <form onSubmit={handleSubmit} className="mt-4 flex items-center gap-2 border-t border-border pt-4">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="How did we do yesterday?"
          className="min-w-0 flex-1 rounded-(--radius-full) border border-border bg-surface-sunken px-4 py-2.5 text-sm text-text placeholder:text-text-tertiary focus:border-border-strong focus:outline-none"
        />
        <button
          type="submit"
          disabled={!draft.trim() || isSending}
          className="rounded-(--radius-full) bg-accent px-4 py-2.5 text-sm font-medium text-accent-fg disabled:opacity-40"
        >
          Ask
        </button>
      </form>
    </div>
  )
}
