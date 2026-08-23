import { useEffect, useRef } from 'react'
import { useChatWidgetStore, type ChatTab } from '@/store/chatWidgetStore'
import { useChat } from '@/hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { cn } from '@/lib/cn'

const STYLIST_PROMPTS = [
  'What should I pack for Sylhet in monsoon?',
  "I'm headed to Cox's Bazar, what should I wear?",
  'Something casual for a hot day',
]
const SUPPORT_QUICK_ACTIONS = ['Track my order', 'Start a return', 'Refund status']

function EmptyState({ tab, onPick }: { tab: ChatTab; onPick: (text: string) => void }) {
  const prompts = tab === 'stylist' ? STYLIST_PROMPTS : SUPPORT_QUICK_ACTIONS
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-sm text-text-secondary">
        {tab === 'stylist'
          ? 'Tell me where you’re headed or what you’re shopping for, and I’ll pull together some picks.'
          : 'Ask about an order, a return, a refund, or anything else about your account.'}
      </p>
      <div className="flex flex-col gap-1.5">
        {prompts.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPick(p)}
            className="rounded-(--radius-full) border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-border-strong hover:text-text"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  )
}

function ChatTabPanel({ tab }: { tab: ChatTab }) {
  const { messages, draft, setDraft, sendMessage, isSending } = useChat(tab)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void sendMessage(draft)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {messages.length === 0 ? (
        <EmptyState tab={tab} onPick={(text) => void sendMessage(text)} />
      ) : (
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-3" aria-live="polite">
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} onFollowup={(text) => void sendMessage(text)} />
          ))}
        </div>
      )}
      <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-2.5">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={tab === 'stylist' ? 'Ask about your trip…' : 'How can we help?'}
          className="min-w-0 flex-1 rounded-(--radius-full) border border-border bg-surface-sunken px-3.5 py-2 text-sm text-text placeholder:text-text-tertiary focus:border-border-strong focus:outline-none"
        />
        <button
          type="submit"
          disabled={!draft.trim() || isSending}
          aria-label="Send message"
          className="flex size-9 shrink-0 items-center justify-center rounded-(--radius-full) bg-accent text-accent-fg disabled:opacity-40"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M3 20l18-8L3 4v6l12 2-12 2z" />
          </svg>
        </button>
      </form>
    </div>
  )
}

export function ChatPanel() {
  const activeTab = useChatWidgetStore((s) => s.activeTab)
  const setActiveTab = useChatWidgetStore((s) => s.setActiveTab)
  const hasUnreadSupport = useChatWidgetStore((s) => s.tabs.support.hasUnread)
  const hasUnreadStylist = useChatWidgetStore((s) => s.tabs.stylist.hasUnread)
  const close = useChatWidgetStore((s) => s.close)

  return (
    <div
      role="dialog"
      aria-label="Chat"
      className="fixed inset-0 z-50 flex flex-col bg-surface sm:inset-auto sm:bottom-24 sm:right-6 sm:h-[620px] sm:w-[400px] sm:rounded-(--radius-lg) sm:border sm:border-border sm:shadow-(--shadow-2)"
    >
      <div className="flex items-center justify-between border-b border-border p-3">
        <div role="tablist" aria-label="Chat tabs" className="flex gap-1 rounded-(--radius-full) bg-surface-sunken p-1">
          {(['stylist', 'support'] as const).map((tab) => (
            <button
              key={tab}
              role="tab"
              aria-selected={activeTab === tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'relative rounded-(--radius-full) px-3 py-1.5 text-xs font-medium',
                activeTab === tab ? 'bg-accent text-accent-fg' : 'text-text-secondary',
              )}
            >
              {tab === 'stylist' ? '✨ Stylist' : '💬 Help'}
              {((tab === 'stylist' && hasUnreadStylist) || (tab === 'support' && hasUnreadSupport)) &&
              activeTab !== tab ? (
                <span className="absolute -right-0.5 -top-0.5 size-2 rounded-full bg-danger" aria-label="Unread" />
              ) : null}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={close}
          aria-label="Close chat"
          className="flex size-8 items-center justify-center rounded-(--radius) text-text-secondary hover:bg-surface-raised hover:text-text"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      {/* Both tabs stay mounted (display:none on the inactive one) rather than conditionally
          rendering just the active one — spec §8.1 requires scroll position to survive a tab
          switch, which an unmount/remount would silently lose even though the message state
          itself lives in the zustand store either way. */}
      <div className={cn('flex min-h-0 flex-1 flex-col', activeTab !== 'stylist' && 'hidden')}>
        <ChatTabPanel tab="stylist" />
      </div>
      <div className={cn('flex min-h-0 flex-1 flex-col', activeTab !== 'support' && 'hidden')}>
        <ChatTabPanel tab="support" />
      </div>
    </div>
  )
}
