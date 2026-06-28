import { useState, useRef, useEffect, useCallback } from 'react'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHeader } from '@/components/UI'
import DateRangeInput from '@/components/DateRangeInput'
import { formatPct, formatNumber } from '@/utils/format'
import type { AIStrategyGenerateResponse } from '@/types'

interface Message {
  id: number
  role: 'user' | 'ai'
  content: string
  result?: AIStrategyGenerateResponse
}

const EXAMPLE_PROMPTS = [
  '做一个5日和20日均线金叉买入、死叉卖出的策略，止损5%',
  '当RSI低于30时买入，高于70时卖出',
  '做一个MACD金叉买入、死叉卖出的策略',
  '做一个突破20日最高价买入、跌破10日最低价卖出的海龟策略',
  '做一个布林带下轨买入、上轨卖出的策略，止损3%',
]

export default function AIStrategy() {
  const { showToast, showLoading: showGlobalLoading, hideLoading } = useApp()
  const chatEndRef = useRef<HTMLDivElement>(null)

  const [symbol, setSymbol] = useState('600522')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [generating, setGenerating] = useState(false)
  const [nextId, setNextId] = useState(1)
  const [codeExpanded, setCodeExpanded] = useState<Record<number, boolean>>({})

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = useCallback(async () => {
    const prompt = input.trim()
    if (!prompt || generating) return

    const userMsg: Message = { id: nextId, role: 'user', content: prompt }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setNextId(n => n + 1)

    setGenerating(true)
    showGlobalLoading('AI 正在生成策略...')
    try {
      const result = await api.generateStrategy({
        prompt,
        symbol,
        start: startDate || undefined,
        end: endDate || undefined,
      })

      const aiMsg: Message = {
        id: nextId + 1,
        role: 'ai',
        content: result.error || `已生成: ${result.display_name}`,
        result: result.error ? undefined : result,
      }
      setMessages(prev => [...prev, aiMsg])
      setNextId(n => n + 2)

      if (result.error) showToast(result.error, 'error')
    } catch (err) {
      showToast('生成失败: ' + (err as Error).message, 'error')
    } finally {
      setGenerating(false)
      hideLoading()
    }
  }, [input, generating, symbol, startDate, endDate, nextId])

  const handleSave = useCallback(async (r: AIStrategyGenerateResponse) => {
    showGlobalLoading('正在保存策略...')
    try {
      const res = await api.saveStrategy({ name: r.name, python_code: r.python_code, yaml_code: r.yaml_code })
      if (res.error) showToast(res.error, 'error')
      else showToast(`策略 ${res.name} 已保存`)
    } catch (err) {
      showToast('保存失败: ' + (err as Error).message, 'error')
    } finally { hideLoading() }
  }, [])

  const handleDelete = useCallback(async (name: string) => {
    showGlobalLoading('正在删除策略...')
    try {
      const res = await api.deleteStrategy(name)
      if (res.error) showToast(res.error, 'error')
      else showToast(`策略 ${res.name} 已删除`)
    } catch (err) {
      showToast('删除失败: ' + (err as Error).message, 'error')
    } finally { hideLoading() }
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      <PageHeader title="AI 策略工坊" subtitle="用自然语言描述交易想法，AI 自动生成策略代码并回测验证" />

      <div style={{ display: 'flex', gap: 16, flex: 1, minHeight: 0 }}>
        <div className="card" style={{ width: 240, flexShrink: 0, overflow: 'auto' }}>
          <div className="card-header"><span className="card-title">回测设置</span></div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">股票代码</label>
              <input type="text" className="form-input" value={symbol}
                onChange={e => setSymbol(e.target.value)} placeholder="600522" />
            </div>
            <div className="form-group">
              <label className="form-label">日期范围</label>
              <DateRangeInput startDate={startDate} endDate={endDate}
                onChange={(s, e) => { setStartDate(s); setEndDate(e) }} />
            </div>
            <div style={{ marginTop: 8 }}>
              <label className="form-label" style={{ marginBottom: 8 }}>💡 试试这些</label>
              {EXAMPLE_PROMPTS.map((p, i) => (
                <button key={i} className="btn btn-ghost"
                  style={{ width: '100%', textAlign: 'left', marginBottom: 4, fontSize: 12, padding: '6px 8px' }}
                  onClick={() => setInput(p)}>{p}</button>
              ))}
            </div>
          </div>
        </div>

        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <div className="card-body" style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
            {messages.length === 0 ? (
              <div className="empty-state" style={{ marginTop: 80 }}>
                <p style={{ fontSize: 48, marginBottom: 8 }}>🤖</p>
                <p style={{ fontSize: 16, color: 'var(--text-primary)' }}>AI 策略工坊</p>
                <p>在下方输入你的策略想法，或点击左侧示例开始</p>
              </div>
            ) : (
              messages.map(msg => (
                <div key={msg.id} style={{
                  display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 16,
                }}>
                  <div style={{
                    maxWidth: '85%', padding: '12px 16px', borderRadius: 'var(--radius-md)',
                    background: msg.role === 'user' ? 'var(--primary)' : 'var(--bg-card-hover)',
                    color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                  }}>
                    <div style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    {msg.result && (
                      <div style={{ marginTop: 12 }}>
                        {msg.result.backtest && (
                          <div className="stats-grid" style={{ marginTop: 8, marginBottom: 12 }}>
                            <div className="stat-card" style={{ minWidth: 90 }}>
                              <div className="stat-label">收益率</div>
                              <div className={'stat-value ' + (msg.result.backtest.return_pct >= 0 ? 'stat-positive' : 'stat-negative')} style={{ fontSize: 16 }}>
                                {formatPct(msg.result.backtest.return_pct)}
                              </div>
                            </div>
                            <div className="stat-card" style={{ minWidth: 70 }}>
                              <div className="stat-label">胜率</div>
                              <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>{formatPct(msg.result.backtest.win_rate)}</div>
                            </div>
                            <div className="stat-card" style={{ minWidth: 70 }}>
                              <div className="stat-label">夏普</div>
                              <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>{formatNumber(msg.result.backtest.sharpe_ratio, 2)}</div>
                            </div>
                            <div className="stat-card" style={{ minWidth: 90 }}>
                              <div className="stat-label">最大回撤</div>
                              <div className="stat-value stat-negative" style={{ fontSize: 14 }}>{formatPct(msg.result.backtest.max_drawdown_pct)}</div>
                            </div>
                          </div>
                        )}
                        <div>
                          <button className="params-toggle"
                            onClick={() => setCodeExpanded(prev => ({ ...prev, [msg.id]: !prev[msg.id] }))}>
                            <span className="toggle-icon">{codeExpanded[msg.id] ? '▼' : '▶'}</span> 策略代码
                          </button>
                          {codeExpanded[msg.id] && (
                            <pre style={{ background: 'var(--bg-card)', padding: 12, borderRadius: 'var(--radius-sm)', fontSize: 11, maxHeight: 300, overflow: 'auto', marginTop: 8 }}>
                              <code>{msg.result.python_code}</code>
                            </pre>
                          )}
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                          <button className="btn btn-primary btn-sm" onClick={() => send()} style={{ fontSize: 12 }}>🔄 重新回测</button>
                          <button className="btn btn-success btn-sm" onClick={() => handleSave(msg.result!)} style={{ fontSize: 12 }}>💾 保存策略</button>
                          <button className="btn btn-danger btn-sm" onClick={() => handleDelete(msg.result!.name)} style={{ fontSize: 12 }}>🗑 删除</button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {generating && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 16 }}>
                <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-md)', background: 'var(--bg-card-hover)' }}>
                  🤖 AI 正在生成策略...
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>
      </div>

      <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
        <input type="text" className="form-input" style={{ flex: 1, padding: '10px 14px', fontSize: 14 }}
          placeholder="输入你的策略想法，如「做一个5日10日均线金叉买入、死叉卖出的策略」..."
          value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown} disabled={generating} />
        <button className="btn btn-primary" onClick={send} disabled={generating || !input.trim()}
          style={{ padding: '10px 24px', fontSize: 14 }}>发送</button>
      </div>
    </div>
  )
}
