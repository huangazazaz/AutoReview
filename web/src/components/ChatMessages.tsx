
import { useRef, useEffect } from 'react'
import type { ChatMessage as ChatMessageType } from '@/types'
import ChatBubble from './ChatBubble'

interface ChatMessagesProps {
  messages: ChatMessageType[]
  onCodeExpand: (id: number) => void
}

export default function ChatMessages({ messages, onCodeExpand }: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
      {messages.length === 0 ? (
        <div className="empty-state-enhanced" style={{ marginTop: 60 }}>
          <div className="empty-icon-bg">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 1 4 4v1h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2V6a4 4 0 0 1 4-4Z"/>
              <circle cx="12" cy="14" r="2" fill="currentColor" fillOpacity="0.5"/>
              <path d="M12 3v3"/>
            </svg>
          </div>
          <div className="empty-title">AI 策略对话</div>
          <div className="empty-desc">在下方输入你的策略想法，AI 将自动生成策略代码并运行回测验证。</div>
        </div>
      ) : (
        messages.map(msg => (
          <ChatBubble key={msg.id} message={msg} onCodeExpand={onCodeExpand} />
        ))
      )}
      <div ref={bottomRef} />
    </div>
  )
}
