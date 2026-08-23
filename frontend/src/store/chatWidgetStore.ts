import { create } from 'zustand'
import type { ChatMessage } from '@/types/chat'

// chat_spec.md §8.1: "Two independent session_ids, created lazily on first message per tab" and
// "Switching preserves scroll position and draft input per tab" — everything here is keyed by
// tab so switching never loses state, matching that requirement directly.
export type ChatTab = 'stylist' | 'support'

interface TabState {
  sessionId: string | null
  messages: ChatMessage[]
  draft: string
  hasUnread: boolean
}

function emptyTab(): TabState {
  return { sessionId: null, messages: [], draft: '', hasUnread: false }
}

interface ChatWidgetState {
  isOpen: boolean
  activeTab: ChatTab
  tabs: Record<ChatTab, TabState>
  open: () => void
  close: () => void
  setActiveTab: (tab: ChatTab) => void
  setSessionId: (tab: ChatTab, sessionId: string) => void
  setDraft: (tab: ChatTab, draft: string) => void
  addMessage: (tab: ChatTab, message: ChatMessage) => void
  updateMessage: (tab: ChatTab, id: string, patch: Partial<ChatMessage>) => void
  appendContent: (tab: ChatTab, id: string, delta: string) => void
  appendBlock: (tab: ChatTab, id: string, block: ChatMessage['blocks'][number]) => void
  markUnread: (tab: ChatTab) => void
}

export const useChatWidgetStore = create<ChatWidgetState>((set) => ({
  isOpen: false,
  activeTab: 'stylist',
  tabs: { stylist: emptyTab(), support: emptyTab() },
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  setActiveTab: (tab) =>
    set((state) => ({
      activeTab: tab,
      tabs: { ...state.tabs, [tab]: { ...state.tabs[tab], hasUnread: false } },
    })),
  setSessionId: (tab, sessionId) =>
    set((state) => ({ tabs: { ...state.tabs, [tab]: { ...state.tabs[tab], sessionId } } })),
  setDraft: (tab, draft) => set((state) => ({ tabs: { ...state.tabs, [tab]: { ...state.tabs[tab], draft } } })),
  addMessage: (tab, message) =>
    set((state) => ({
      tabs: { ...state.tabs, [tab]: { ...state.tabs[tab], messages: [...state.tabs[tab].messages, message] } },
    })),
  updateMessage: (tab, id, patch) =>
    set((state) => ({
      tabs: {
        ...state.tabs,
        [tab]: {
          ...state.tabs[tab],
          messages: state.tabs[tab].messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
        },
      },
    })),
  appendContent: (tab, id, delta) =>
    set((state) => ({
      tabs: {
        ...state.tabs,
        [tab]: {
          ...state.tabs[tab],
          messages: state.tabs[tab].messages.map((m) => (m.id === id ? { ...m, content: m.content + delta } : m)),
        },
      },
    })),
  appendBlock: (tab, id, block) =>
    set((state) => ({
      tabs: {
        ...state.tabs,
        [tab]: {
          ...state.tabs[tab],
          messages: state.tabs[tab].messages.map((m) => (m.id === id ? { ...m, blocks: [...m.blocks, block] } : m)),
        },
      },
    })),
  markUnread: (tab) =>
    set((state) => ({ tabs: { ...state.tabs, [tab]: { ...state.tabs[tab], hasUnread: true } } })),
}))
