import { fetchEventSource } from '@microsoft/fetch-event-source'
import { apiClient } from './apiClient'
import type { ChatAgent, ChatBlock, ChatResponse, ChatSession, ChatToolTrace } from '@/types/chat'
import type { Envelope } from '@/types/catalog'

export async function createChatSession(agent: ChatAgent): Promise<ChatSession> {
  const { data } = await apiClient.post<Envelope<ChatSession>>(`/chat/${agent}/session`, { agent })
  return data.data
}

export async function sendChatMessage(agent: ChatAgent, sessionId: string, message: string): Promise<ChatResponse> {
  const { data } = await apiClient.post<Envelope<ChatResponse>>(`/chat/${agent}`, {
    session_id: sessionId,
    message,
    stream: false,
  })
  return data.data
}

function readCookie(name: string): string | undefined {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : undefined
}

export interface StreamHandlers {
  onToolStart?: (server: string, tool: string) => void
  onToolEnd?: (tool: string, ms: number, ok: boolean) => void
  onToken?: (delta: string) => void
  onBlock?: (block: ChatBlock) => void
  onDone?: (payload: { message_id: string; session_id: string; tool_trace: ChatToolTrace[]; relaxation_applied?: string[] }) => void
  onError?: (message: string) => void
}

/** POST-based SSE (chat_spec.md §7.1) — the browser's native EventSource can't send a POST body,
 * which is why this uses @microsoft/fetch-event-source (spec §11.2's own choice) instead. */
export async function streamChatMessage(
  agent: ChatAgent,
  sessionId: string,
  message: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const csrfToken = readCookie('csrf_token')
  await fetchEventSource(`/api/v1/chat/${agent}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': crypto.randomUUID(),
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    },
    body: JSON.stringify({ session_id: sessionId, message, stream: true }),
    credentials: 'include',
    signal,
    openWhenHidden: true, // a chat reply shouldn't stall just because the tab lost focus
    async onopen(response) {
      if (!response.ok) throw new Error(`Chat stream failed to open (${response.status})`)
    },
    onmessage(ev) {
      if (!ev.data) return
      const data = JSON.parse(ev.data)
      switch (ev.event) {
        case 'tool_start':
          handlers.onToolStart?.(data.server, data.tool)
          break
        case 'tool_end':
          handlers.onToolEnd?.(data.tool, data.ms, data.ok)
          break
        case 'token':
          handlers.onToken?.(data.delta)
          break
        case 'block':
          handlers.onBlock?.(data as ChatBlock)
          break
        case 'done':
          handlers.onDone?.(data)
          break
        case 'error':
          handlers.onError?.(data.error?.message ?? 'Something went wrong.')
          break
      }
    },
    onerror(err) {
      handlers.onError?.('Connection lost. Please try again.')
      throw err // stop fetchEventSource's own retry loop — the caller decides whether to retry
    },
  })
}
