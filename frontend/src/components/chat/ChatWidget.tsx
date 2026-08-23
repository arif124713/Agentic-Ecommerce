import { useEffect, useRef } from 'react'
import { useChatWidgetStore } from '@/store/chatWidgetStore'
import { ChatPanel } from './ChatPanel'
import { cn } from '@/lib/cn'

// chat_spec.md §8.1: floating launcher, bottom-right. §8.3: focus trap while open, Esc closes
// and restores focus to the launcher, `prefers-reduced-motion` disables the shimmer (handled by
// the pending-state dots in MessageBubble using Tailwind's `animate-bounce`, which already
// respects `prefers-reduced-motion` via this project's global reduced-motion CSS — no extra work
// needed here).
export function ChatWidget() {
  const isOpen = useChatWidgetStore((s) => s.isOpen)
  const open = useChatWidgetStore((s) => s.open)
  const close = useChatWidgetStore((s) => s.close)
  const hasUnread = useChatWidgetStore((s) => s.tabs.stylist.hasUnread || s.tabs.support.hasUnread)
  const launcherRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    panelRef.current?.querySelector<HTMLElement>('input, button')?.focus()

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close()
        launcherRef.current?.focus()
        return
      }
      if (e.key !== 'Tab' || !panelRef.current) return
      const focusable = panelRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, close])

  return (
    <>
      <button
        ref={launcherRef}
        type="button"
        onClick={open}
        aria-label="Open chat"
        aria-expanded={isOpen}
        className={cn(
          'fixed bottom-6 right-6 z-40 flex size-14 items-center justify-center rounded-(--radius-full) bg-accent text-accent-fg shadow-(--shadow-2) transition-transform hover:scale-105',
          isOpen && 'hidden',
        )}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" />
        </svg>
        {hasUnread ? (
          <span className="absolute right-0.5 top-0.5 size-3 rounded-full border-2 border-bg bg-danger" aria-label="Unread messages" />
        ) : null}
      </button>
      {isOpen ? <div ref={panelRef}><ChatPanel /></div> : null}
    </>
  )
}
