import type { ChatSession } from '@/types'

interface ChatSessionListProps {
  sessions: ChatSession[]
  activeSessionId?: string
  onSelect: (sessionId: string) => void
  onNew: () => void
  onDelete: (sessionId: string) => void
  onPromptFill?: (text: string) => void
}

const EXAMPLE_PROMPTS = [
  { icon: '📊', text: '做一个5日和20日均线金叉买入、死叉卖出的策略，止损5%' },
  { icon: '📉', text: '当RSI低于30时买入，高于70时卖出' },
  { icon: '📈', text: '做一个MACD金叉买入、死叉卖出的策略' },
  { icon: '🐢', text: '做一个突破20日最高价买入、跌破10日最低价卖出的海龟策略' },
  { icon: '📐', text: '做一个布林带下轨买入、上轨卖出的策略，止损3%' },
]

export default function ChatSessionList({
  sessions, activeSessionId, onSelect, onNew, onDelete, onPromptFill,
}: ChatSessionListProps) {
  return (
    <div className="card card-accent" style={{
      width: 260, flexShrink: 0, overflow: 'auto',
      borderTop: '2px solid rgba(139,92,246,0.3)',
      display: 'flex', flexDirection: 'column',
    }}>
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: 'var(--accent)' }}>💬</span> 会话
        </span>
        <button className="btn btn-ghost btn-sm" onClick={onNew}
          style={{ fontSize: 18, padding: '2px 8px', lineHeight: 1 }}>
          +
        </button>
      </div>
      <div className="card-body" style={{ flex: 1, overflow: 'auto', padding: '8px 12px' }}>
        {sessions.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '20px 0' }}>
            暂无会话，发送消息自动创建
          </div>
        ) : (
          sessions.map(s => (
            <div key={s.session_id} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '10px 12px', borderRadius: 'var(--radius)',
              cursor: 'pointer', marginBottom: 4,
              background: s.session_id === activeSessionId
                ? 'rgba(139,92,246,0.12)'
                : 'transparent',
              border: s.session_id === activeSessionId
                ? '1px solid rgba(139,92,246,0.25)'
                : '1px solid transparent',
            }} onClick={() => onSelect(s.session_id)}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.title || '新会话'}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                  {s.message_count} 条消息
                </div>
              </div>
              <button className="btn btn-ghost btn-sm"
                onClick={e => { e.stopPropagation(); onDelete(s.session_id) }}
                style={{ fontSize: 14, padding: '2px 6px', color: 'var(--text-muted)' }}
                title="删除会话">
                🗑
              </button>
            </div>
          ))
        )}

        <div style={{ marginTop: 16 }}>
          <label className="form-label" style={{
            marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4,
            fontSize: 11, color: 'var(--text-muted)',
          }}>
            <span>💡</span> 试试这些
          </label>
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button key={i} className="btn btn-ghost"
              style={{
                width: '100%', textAlign: 'left', marginBottom: 4, fontSize: 12,
                padding: '8px 10px', lineHeight: 1.5,
                border: '1px solid var(--border-light)', borderRadius: 'var(--radius)',
              }}
              onClick={() => { onNew(); onPromptFill?.(p.text) }}>
              <span style={{ marginRight: 6 }}>{p.icon}</span>{p.text}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
