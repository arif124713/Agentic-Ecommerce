import type { ChatMessage } from '@/types/chat'
import { renderChatBlock } from './ChatBlocks'
import { cn } from '@/lib/cn'

interface MessageBubbleProps {
  message: ChatMessage
  onFollowup: (text: string) => void
}

export function MessageBubble({ message, onFollowup }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex flex-col gap-2', isUser && 'items-end')}>
      <div
        className={cn(
          'max-w-[85%] rounded-(--radius) px-3 py-2 text-sm',
          isUser ? 'bg-accent text-accent-fg' : 'bg-surface-raised text-text',
        )}
      >
        {message.pending && !message.content ? (
          <span className="flex items-center gap-1" aria-live="polite" aria-label="Assistant is typing">
            <span className="size-1.5 animate-bounce rounded-full bg-text-tertiary [animation-delay:-0.3s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-text-tertiary [animation-delay:-0.15s]" />
            <span className="size-1.5 animate-bounce rounded-full bg-text-tertiary" />
          </span>
        ) : (
          <p className="whitespace-pre-wrap">{message.content}</p>
        )}
      </div>
      {message.blocks.length > 0 ? (
        <div className="w-full max-w-[95%] space-y-2" aria-live={isUser ? undefined : 'polite'}>
          {message.blocks.map((block, i) => renderChatBlock(block, `${message.id}-${i}`, onFollowup))}
        </div>
      ) : null}
    </div>
  )
}
