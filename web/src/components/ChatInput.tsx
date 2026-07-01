import { useState, useCallback, useEffect, useRef, type KeyboardEvent } from 'react'

interface ChatInputProps {
  symbol: string
  startDate: string
  endDate: string
  onSymbolChange: (s: string) => void
  onStartDateChange: (d: string) => void
  onEndDateChange: (d: string) => void
  onSend: (text: string) => void
  disabled: boolean
  fillText?: string
  onFillConsumed?: () => void
}

const EXAMPLE_PROMPTS = [
  { icon: '📊', text: '做一个5日和20日均线金叉买入、死叉卖出的策略，止损5%' },
  { icon: '📉', text: '当RSI低于30时买入，高于70时卖出' },
  { icon: '📈', text: '做一个MACD金叉买入、死叉卖出的策略' },
  { icon: '🐢', text: '做一个突破20日最高价买入、跌破10日最低价卖出的海龟策略' },
  { icon: '📐', text: '做一个布林带下轨买入、上轨卖出的策略，止损3%' },
]

export default function ChatInput({
  symbol, startDate, endDate,
  onSymbolChange, onStartDateChange, onEndDateChange,
  onSend, disabled, fillText, onFillConsumed,
}: ChatInputProps) {
  const [input, setInput] = useState('')
  const [promptIndex, setPromptIndex] = useState(0)
  const [isLeaving, setIsLeaving] = useState(false)
  const consumedRef = useRef<string | undefined>()
  const timerRef = useRef<ReturnType<typeof setInterval>>()

  // Auto-rotate prompts every 2s
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setIsLeaving(true)
      setTimeout(() => {
        setPromptIndex(i => (i + 1) % EXAMPLE_PROMPTS.length)
        setIsLeaving(false)
      }, 300)
    }, 2000)
    return () => clearInterval(timerRef.current)
  }, [])

  // External fill via onPromptFill prop
  useEffect(() => {
    if (fillText && fillText !== consumedRef.current) {
      consumedRef.current = fillText
      setInput(fillText)
      onFillConsumed?.()
    }
  }, [fillText, onFillConsumed])

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

  const handlePromptClick = useCallback((text: string) => {
    setInput(text)
  }, [])

  const current = EXAMPLE_PROMPTS[promptIndex]

  return (
    <div>
      {/* ── 滚动提示轮播 ── */}
      <button
        onClick={() => handlePromptClick(current.text)}
        title="点击填入输入框"
        style={{
          width: '100%', textAlign: 'left', marginBottom: 8, fontSize: 13,
          padding: '8px 14px', lineHeight: 1.5, cursor: 'pointer',
          background: 'rgba(139,92,246,0.06)',
          border: '1px solid rgba(139,92,246,0.15)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-sans)',
          display: 'flex', alignItems: 'center', gap: 8,
          opacity: isLeaving ? 0 : 1,
          transform: isLeaving ? 'translateY(-6px)' : 'translateY(0)',
          transition: 'opacity 0.25s ease, transform 0.25s ease',
        }}
      >
        <span style={{ fontSize: 16, flexShrink: 0 }}>{current.icon}</span>
        <span style={{ flex: 1 }}>{current.text}</span>
        <span style={{
          fontSize: 10, color: 'var(--text-muted)', flexShrink: 0,
          background: 'var(--bg-input)', padding: '2px 8px', borderRadius: 10,
        }}>
          点击填入
        </span>
      </button>

      {/* ── 输入区 ── */}
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
    </div>
  )
}
