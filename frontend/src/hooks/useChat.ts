import { useCallback, useState } from 'react'
import axios from 'axios'
import { createChatSession, streamChatMessage } from '@/services/chat'
import { useChatWidgetStore, type ChatTab } from '@/store/chatWidgetStore'

function describeError(error: unknown, tab: ChatTab): string {
  if (axios.isAxiosError(error) && error.response?.status === 401) {
    return tab === 'support'
      ? 'Please log in to chat with support — you can still browse and add to cart as a guest.'
      : "Your session expired — go ahead and ask again, I'll pick up from here."
  }
  return "Couldn't reach the assistant. Please try again."
}

export function useChat(tab: ChatTab) {
  const tabState = useChatWidgetStore((s) => s.tabs[tab])
  const addMessage = useChatWidgetStore((s) => s.addMessage)
  const updateMessage = useChatWidgetStore((s) => s.updateMessage)
  const appendContent = useChatWidgetStore((s) => s.appendContent)
  const appendBlock = useChatWidgetStore((s) => s.appendBlock)
  const setSessionId = useChatWidgetStore((s) => s.setSessionId)
  const setDraft = useChatWidgetStore((s) => s.setDraft)
  const markUnread = useChatWidgetStore((s) => s.markUnread)
  const [isSending, setIsSending] = useState(false)

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isSending) return

      setIsSending(true)
      addMessage(tab, { id: crypto.randomUUID(), role: 'user', content: trimmed, blocks: [] })
      setDraft(tab, '')

      const assistantId = crypto.randomUUID()
      addMessage(tab, { id: assistantId, role: 'assistant', content: '', blocks: [], pending: true })

      try {
        let sessionId = useChatWidgetStore.getState().tabs[tab].sessionId
        if (!sessionId) {
          const session = await createChatSession(tab)
          sessionId = session.session_id
          setSessionId(tab, sessionId)
        }

        await streamChatMessage(tab, sessionId, trimmed, {
          // Real token-by-token streaming — each call is a genuine fragment of the reply as
          // DeepSeek streams it (see backend/app/agents/runtime.py), so this appends.
          onToken: (delta) => appendContent(tab, assistantId, delta),
          onBlock: (block) => appendBlock(tab, assistantId, block),
          onDone: () => {
            updateMessage(tab, assistantId, { pending: false })
            const state = useChatWidgetStore.getState()
            if (state.activeTab !== tab || !state.isOpen) markUnread(tab)
          },
          onError: (message) => updateMessage(tab, assistantId, { content: message, pending: false }),
        })
      } catch (error) {
        updateMessage(tab, assistantId, { content: describeError(error, tab), pending: false })
      } finally {
        setIsSending(false)
      }
    },
    [tab, isSending, addMessage, setDraft, setSessionId, updateMessage, appendContent, appendBlock, markUnread],
  )

  return {
    messages: tabState.messages,
    draft: tabState.draft,
    setDraft: (value: string) => setDraft(tab, value),
    sendMessage,
    isSending,
  }
}
