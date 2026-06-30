import type { ChatMessage, StrategyResult } from '@/types'
import StrategyCard from './StrategyCard'

interface ChatBubbleProps {
  message: ChatMessage
  onCodeExpand: (id: number) => void
  onSave?: (strategy: StrategyResult) => void
  onDelete?: (name: string) => void
  onCopy?: (code: string) => void
}

export default function ChatBubble({ message, onCodeExpand, onSave, onDelete, onCopy }: ChatBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 16,
    }}>
      <div style={{
        maxWidth: '85%',
        padding: '14px 18px',
        borderRadius: 'var(--radius-lg)',
        background: isUser
          ? 'linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%)'
          : 'linear-gradient(135deg, rgba(30,41,59,0.95) 0%, rgba(40,53,72,0.95) 100%)',
        color: isUser ? '#fff' : 'var(--text-primary)',
        border: isUser ? 'none' : '1px solid var(--border-light)',
        boxShadow: isUser
          ? '0 4px 16px rgba(139,92,246,0.25)'
          : 'var(--shadow-sm)',
      }}>
        <div style={{ fontSize: 13, whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>
          {message.content}
        </div>
        {(message.strategy || message.backtest) && (
          <StrategyCard
            messageId={message.id}
            strategy={message.strategy}
            backtest={message.backtest}
            codeExpanded={message.codeExpanded || false}
            onCodeExpand={onCodeExpand}
            onSave={onSave}
            onDelete={onDelete}
            onCopy={onCopy}
          />
        )}
      </div>
    </div>
  )
}
