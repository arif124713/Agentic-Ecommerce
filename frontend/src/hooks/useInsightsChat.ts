import { useCallback, useRef, useState } from 'react'
import { createChatSession, streamChatMessage } from '@/services/chat'
import type { ChatBlock, ChatMessage } from '@/types/chat'

// Deliberately separate from useChat.ts/chatWidgetStore.ts: Insights is a single full-page agent
// (spec §8.2's /admin/ask), not one of the widget's two tabs — it doesn't need tab state, unread
// badges, or cross-navigation persistence, so plain component state is the right amount of
// machinery rather than forcing it through the tab-shaped store.
export function useInsightsChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const sessionIdRef = useRef<string | null>(null)

  const updateMessage = (id: string, patch: Partial<ChatMessage>) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))

  const appendBlock = (id: string, block: ChatBlock) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, blocks: [...m.blocks, block] } : m)))

  const appendContent = (id: string, delta: string) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, content: m.content + delta } : m)))

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return

    setIsSending(true)
    setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: trimmed, blocks: [] }])
    setDraft('')

    const assistantId = crypto.randomUUID()
    setMessages((prev) => [...prev, { id: assistantId, role: 'assistant', content: '', blocks: [], pending: true }])

    try {
      if (!sessionIdRef.current) {
        const session = await createChatSession('insights')
        sessionIdRef.current = session.session_id
      }

      await streamChatMessage('insights', sessionIdRef.current, trimmed, {
        onToken: (delta) => appendContent(assistantId, delta),
        onBlock: (block) => appendBlock(assistantId, block),
        onDone: () => updateMessage(assistantId, { pending: false }),
        onError: (message) => updateMessage(assistantId, { content: message, pending: false }),
      })
    } catch {
      updateMessage(assistantId, { content: "Couldn't reach the assistant. Please try again.", pending: false })
    } finally {
      setIsSending(false)
    }
  }, [])

  return { messages, draft, setDraft, sendMessage, isSending }
}
