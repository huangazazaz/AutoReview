import { useRef, useEffect } from 'react'
import type { ChatMessage as ChatMessageType, StrategyResult } from '@/types'
import ChatBubble from './ChatBubble'

interface ProgressStep {
  step: string
  message: string
}

interface ChatMessagesProps {
  messages: ChatMessageType[]
  onCodeExpand: (id: number) => void
  onSave?: (strategy: StrategyResult) => void
  onDelete?: (name: string) => void
  onCopy?: (code: string) => void
  sending?: boolean
  progressSteps?: ProgressStep[]
}

const STEP_ICONS: Record<string, string> = {
  generating: '⏳',
  generated: '✅',
  backtesting: '⏳',
  backtest_ok: '✅',
  fixing: '🔧',
  failed: '❌',
}

export default function ChatMessages({
  messages,
  onCodeExpand,
  onSave,
  onDelete,
  onCopy,
  sending,
  progressSteps,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending, progressSteps])

  return (
    <div style={{ flex: 1 }}>
      {messages.length === 0 && !sending ? (
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
          <ChatBubble
            key={msg.id}
            message={msg}
            onCodeExpand={onCodeExpand}
            onSave={onSave}
            onDelete={onDelete}
            onCopy={onCopy}
          />
        ))
      )}
      {sending && (
        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
          <div style={{
            padding: '12px 18px', borderRadius: 'var(--radius-lg)',
            background: 'linear-gradient(135deg, rgba(30,41,59,0.95) 0%, rgba(40,53,72,0.95) 100%)',
            border: '1px solid var(--border-light)',
            display: 'flex', flexDirection: 'column', gap: 6,
            minWidth: 280,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></div>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 500 }}>
                AI 正在处理...
              </span>
            </div>
            {progressSteps && progressSteps.length > 0 && (
              <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
                {progressSteps.map((s, i) => (
                  <div key={i} style={{
                    fontSize: 12, color: s.step === 'failed' ? 'var(--danger)' : 'var(--text-muted)',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <span>{STEP_ICONS[s.step] || '⏳'}</span>
                    <span>{s.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
