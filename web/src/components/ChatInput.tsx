import { useState, useCallback, type KeyboardEvent } from 'react'

interface ChatInputProps {
  symbol: string
  startDate: string
  endDate: string
  onSymbolChange: (s: string) => void
  onStartDateChange: (d: string) => void
  onEndDateChange: (d: string) => void
  onSend: (text: string) => void
  disabled: boolean
}

export default function ChatInput({
  symbol, startDate, endDate,
  onSymbolChange, onStartDateChange, onEndDateChange,
  onSend, disabled,
}: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || disabled) return
    onSend(text)
    setInput('')
  }, [input, disabled, onSend])

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div style={{
      display: 'flex', gap: 8, alignItems: 'flex-end',
      background: 'var(--bg-card)', padding: '8px 12px',
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--border-light)',
      boxShadow: 'var(--shadow-sm)',
    }}>
      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
        <div className="form-group" style={{ margin: 0 }}>
          <input type="text" className="form-input"
            style={{ width: 80, padding: '8px 10px', fontSize: 13, textAlign: 'center' }}
            value={symbol} onChange={e => onSymbolChange(e.target.value)}
            placeholder="代码" title="股票代码" />
        </div>
        <div className="form-group" style={{ margin: 0 }}>
          <input type="date" className="form-input"
            style={{ width: 120, padding: '8px 10px', fontSize: 13 }}
            value={startDate} onChange={e => onStartDateChange(e.target.value)}
            title="开始日期" />
        </div>
        <div className="form-group" style={{ margin: 0 }}>
          <input type="date" className="form-input"
            style={{ width: 120, padding: '8px 10px', fontSize: 13 }}
            value={endDate} onChange={e => onEndDateChange(e.target.value)}
            title="结束日期" />
        </div>
      </div>
      <input type="text" className="form-input" style={{
        flex: 1, padding: '8px 12px', fontSize: 14,
        border: 'none', background: 'transparent',
      }}
        placeholder="输入你的策略想法，或对已有策略提出修改..."
        value={input} onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown} disabled={disabled} />
      <button className="btn btn-primary" onClick={handleSend}
        disabled={disabled || !input.trim()}
        style={{ padding: '8px 20px', fontSize: 14, flexShrink: 0 }}>
        {disabled ? '⏳' : '🚀 发送'}
      </button>
    </div>
  )
}
