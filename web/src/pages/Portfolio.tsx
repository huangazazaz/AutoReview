import { useState, useEffect, useCallback } from 'react'
import CreatableSelect from 'react-select/creatable'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHeader } from '@/components/UI'
import DateRangeInput from '@/components/DateRangeInput'
import { formatNumber, formatPct, formatAmount } from '@/utils/format'
import type { StrategyInfo, GroupInfo, PortfolioBacktestResponse, CachedStock } from '@/types'

export default function Portfolio() {
  const { showToast, showLoading: showGlobalLoading, hideLoading } = useApp()

  const [screener, setScreener] = useState('momentum_screener')
  const [strategy, setStrategy] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [inputMode, setInputMode] = useState<'symbols' | 'group'>('symbols')
  const [symbols, setSymbols] = useState('all')
  const [group, setGroup] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [groups, setGroups] = useState<GroupInfo[]>([])
  const [cachedStocks, setCachedStocks] = useState<CachedStock[]>([])
  const [result, setResult] = useState<PortfolioBacktestResponse | null>(null)

  const [paramSchema, setParamSchema] = useState<Record<string, { default?: unknown; type?: string }>>({})
  const [editParams, setEditParams] = useState<Record<string, string>>({})
  const [paramsExpanded, setParamsExpanded] = useState(false)

  useEffect(() => {
    api.getStrategies().then(d => setStrategies(d.strategies))
    api.getGroups().then(d => setGroups(d.groups))
    api.getCachedStocks().then(d => setCachedStocks(d.symbols)).catch(() => {})
  }, [])

  useEffect(() => {
    const found = strategies.find(s => s.name === strategy)
    if (found?.param_schema) {
      setParamSchema(found.param_schema)
      const edits: Record<string, string> = {}
      for (const [k, info] of Object.entries(found.param_schema)) {
        const v = found.params?.[k] ?? info.default ?? ''
        edits[k] = typeof v === 'object' ? JSON.stringify(v) : String(v)
      }
      setEditParams(edits)
    } else {
      setParamSchema({})
      setEditParams({})
      setParamsExpanded(false)
    }
  }, [strategy, strategies])

  const submit = useCallback(async () => {
    const params: any = {
      screener_name: screener,
    }

    if (inputMode === 'group') {
      if (!group) { showToast('请选择分组', 'warning'); return }
      params.group = group
    } else {
      params.symbols = symbols || 'all'
    }

    if (strategy) {
      params.strategy_name = strategy
      const overrides: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(editParams)) {
        if (v === '') continue
        const type = paramSchema[k]?.type
        if (type === 'int') overrides[k] = parseInt(v, 10)
        else if (type === 'float') overrides[k] = parseFloat(v)
        else if (type === 'list' || type === 'dict') {
          try { overrides[k] = JSON.parse(v) } catch { continue }
        } else if (type === 'bool') {
          overrides[k] = v === 'true' || v === 'True'
        } else {
          overrides[k] = v
        }
      }
      if (Object.keys(overrides).length > 0) params.strategy_params = overrides
    }

    if (startDate) params.start = startDate
    if (endDate) params.end = endDate

    setSubmitting(true)
    showGlobalLoading('正在运行组合回测，请稍候...')
    try {
      const data = await api.portfolioBacktest(params)
      if (data.error) {
        showToast(data.error, 'error')
      } else {
        setResult(data)
      }
    } catch (err) {
      showToast('组合回测失败：' + (err as Error).message, 'error')
    } finally {
      setSubmitting(false)
      hideLoading()
    }
  }, [screener, strategy, startDate, endDate, inputMode, symbols, group, editParams, paramSchema])

  const hasParams = strategy && Object.keys(paramSchema).length > 0

  return (
    <>
      {/* 英雄区 */}
      <div className="page-hero">
        <PageHeader title="组合回测" subtitle="单账户多持仓 + 股票筛选 + 策略择时，模拟真实账户收益" />
      </div>

      <div className="card card-accent" style={{ borderTop: '2px solid rgba(139,92,246,0.3)' }}>
        <div className="card-header">
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--accent)' }}>⚙</span> 回测参数
          </span>
        </div>
        <div className="card-body">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="pf-screener">选股筛选器</label>
              <select className="form-select" id="pf-screener" value={screener} onChange={e => setScreener(e.target.value)}>
                <option value="momentum_screener">momentum_screener (动量多因子)</option>
                <option value="hot_money_screener">hot_money_screener (游资)</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="pf-strategy">
                择时策略 <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 11 }}>(可选)</span>
              </label>
              <select className="form-select" id="pf-strategy" value={strategy} onChange={e => setStrategy(e.target.value)}>
                <option value="">— 纯 Screener 模式 —</option>
                {strategies.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
              </select>
            </div>
          </div>

          <div className="tabs" style={{ marginBottom: 16 }}>
            <button className={'tab' + (inputMode === 'symbols' ? ' active' : '')} onClick={() => setInputMode('symbols')}>按代码</button>
            <button className={'tab' + (inputMode === 'group' ? ' active' : '')} onClick={() => setInputMode('group')}>按分组</button>
          </div>

          <div className="form-row">
            {inputMode === 'symbols' ? (
              <div className="form-group" style={{ flex: 2 }}>
                <label className="form-label" htmlFor="pf-symbols">股票代码</label>
                <CreatableSelect
                  id="pf-symbols"
                  isMulti
                  placeholder="输入代码或名称搜索股票，可多选…"
                  options={cachedStocks.map(s => ({
                    value: s.symbol,
                    label: `${s.symbol}${s.name ? ` - ${s.name}` : ''}`
                  }))}
                  value={symbols && symbols !== 'all'
                    ? symbols.split(',').map(s => s.trim().toUpperCase()).filter(Boolean).map(sym => {
                        const found = cachedStocks.find(cs => cs.symbol === sym)
                        return { value: sym, label: found ? `${sym} - ${found.name}` : sym }
                      })
                    : []}
                  onChange={(opts) => {
                    const vals = opts.map(o => o.value)
                    setSymbols(vals.length ? vals.join(',') : 'all')
                  }}
                  onCreateOption={(input) => {
                    const newSym = input.toUpperCase()
                    const current = symbols === 'all' ? [] : symbols.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
                    if (!current.includes(newSym)) {
                      current.push(newSym)
                      setSymbols(current.join(','))
                    }
                  }}
                  filterOption={(opt, input) => {
                    const q = input.toLowerCase()
                    return opt.data.label.toLowerCase().includes(q)
                  }}
                  isClearable
                  isSearchable
                  isLoading={cachedStocks.length === 0}
                  loadingMessage={() => '正在加载股票列表…'}
                  menuPortalTarget={document.body}
                  className="react-select"
                  classNamePrefix="rs"
                  noOptionsMessage={() => '未找到，输入代码后按回车创建'}
                  formatCreateLabel={(v) => `添加 "${v.toUpperCase()}"`}
                />
                <div className="form-hint">直接输入代码可添加任意股票，留空则使用全市场</div>
              </div>
            ) : (
              <div className="form-group" style={{ flex: 2 }}>
                <label className="form-label" htmlFor="pf-group">选择分组</label>
                <select className="form-select" id="pf-group" value={group} onChange={e => setGroup(e.target.value)}>
                  <option value="">— 选择分组 —</option>
                  {groups.map(g => <option key={g.id} value={g.id}>{g.name} ({g.symbols.length} 只)</option>)}
                </select>
              </div>
            )}
            <div className="form-group" style={{ minWidth: 280 }}>
              <label className="form-label">日期范围</label>
              <DateRangeInput startDate={startDate} endDate={endDate}
                onChange={(s, e) => { setStartDate(s); setEndDate(e) }} />
            </div>
            <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-primary" style={{
                width: '100%', minWidth: 140,
                background: submitting ? undefined : 'var(--gradient-brand)',
                border: submitting ? undefined : 'none',
              }} onClick={submit} disabled={submitting}>
                {submitting ? '⏳ 回测中...' : '🚀 开始组合回测'}
              </button>
            </div>
          </div>

          {hasParams && (
            <div className="params-section" style={{ marginTop: 16 }}>
              <button type="button" className="params-toggle"
                onClick={() => setParamsExpanded(!paramsExpanded)} aria-expanded={paramsExpanded}>
                <span className="toggle-icon">{paramsExpanded ? '▼' : '▶'}</span> {strategy} 策略参数
                <span className="params-summary">
                  {Object.entries(paramSchema).slice(0, 5).map(([k]) => {
                    const v = editParams[k] !== undefined ? editParams[k] : '—'
                    return `${k}=${v}`
                  }).join(', ')}
                </span>
              </button>
              {paramsExpanded && (
                <div className="params-body">
                  <div className="param-grid">
                    {Object.entries(paramSchema).map(([key, info]) => {
                      const isSimple = ['int', 'float', 'str', 'bool'].includes(info.type || 'str')
                      return (
                        <div key={key} className={'param-item' + (isSimple ? '' : ' param-item-wide')}>
                          <label className="param-label">{key}{!isSimple && <span className="param-type-tag">{info.type}</span>}</label>
                          {isSimple ? (
                            <input type={info.type === 'int' || info.type === 'float' ? 'number' : 'text'}
                              className="form-input param-input"
                              step={info.type === 'float' ? '0.01' : info.type === 'int' ? '1' : undefined}
                              value={editParams[key] ?? ''}
                              placeholder={info.default !== undefined ? String(info.default) : ''}
                              onChange={e => setEditParams(prev => ({ ...prev, [key]: e.target.value }))}
                            />
                          ) : (
                            <textarea className="form-input param-input" rows={2}
                              value={editParams[key] ?? ''}
                              placeholder={info.default !== undefined ? JSON.stringify(info.default) : ''}
                              onChange={e => setEditParams(prev => ({ ...prev, [key]: e.target.value }))}
                            />
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {result && <PortfolioResult result={result} screener={screener} strategy={strategy} />}
    </>
  )
}

function PortfolioResult({ result, screener, strategy }: {
  result: PortfolioBacktestResponse
  screener: string
  strategy: string
}) {
  const m = result.metrics
  if (!m || Object.keys(m).length === 0) {
    return (
      <div className="card card-accent" style={{ marginTop: 16 }}>
        <div className="card-body">
          <div className="empty-state-enhanced">
            <div className="empty-icon-bg">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 3v18h18"/><path d="M7 16l4-6 4 3 3-5"/>
              </svg>
            </div>
            <div className="empty-title">无回测结果</div>
            <div className="empty-desc">请检查回测参数后重试</div>
          </div>
        </div>
      </div>
    )
  }

  const isProfitable = m.total_return_pct >= 0
  const mode = strategy ? `${screener} + ${strategy}` : `${screener} (纯筛选)`

  return (
    <>
      <div className="stats-grid" style={{ marginTop: 20 }}>
        <div className="stat-card" style={{ borderTop: '2px solid var(--info)' }}>
          <div className="stat-label">🔧 回测模式</div>
          <div className="stat-value stat-neutral" style={{ fontSize: 13, fontFamily: 'var(--font-sans)' }}>{mode}</div>
          <div className="stat-sub">{result.trade_count} 笔交易</div>
        </div>
        <div className="stat-card" style={{ borderTop: `2px solid ${isProfitable ? 'var(--buy)' : 'var(--sell)'}` }}>
          <div className="stat-label">💰 初始资金 → 最终权益</div>
          <div className="stat-value stat-neutral" style={{ fontSize: 18 }}>
            {formatAmount(m.initial_capital)} <span style={{ color: 'var(--text-muted)', fontSize: 14 }}>→</span> {formatAmount(m.final_equity)}
          </div>
          <div className="stat-sub" style={{ color: isProfitable ? 'var(--buy)' : 'var(--sell)' }}>
            {isProfitable ? '🟢 盈利' : '🔴 亏损'} {formatAmount(Math.abs(m.final_equity - m.initial_capital))}
          </div>
        </div>
        <div className="stat-card" style={{ borderTop: `2px solid ${isProfitable ? 'var(--buy)' : 'var(--sell)'}` }}>
          <div className="stat-label">📈 总收益率</div>
          <div className={'stat-value ' + (isProfitable ? 'stat-positive' : 'stat-negative')}>
            {formatPct(m.total_return_pct)}
          </div>
          <div className="stat-sub">最大回撤 {formatPct(m.max_drawdown_pct)}</div>
        </div>
        <div className="stat-card" style={{ borderTop: '2px solid var(--accent)' }}>
          <div className="stat-label">🎯 胜率 / ⚡ 夏普比率</div>
          <div className="stat-value stat-neutral" style={{ fontSize: 20 }}>
            {formatPct(m.win_rate)} <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>/</span> {formatNumber(m.sharpe_ratio, 3)}
          </div>
          <div className="stat-sub">{m.total_trades} 笔交易</div>
        </div>
      </div>

      <div className="card card-accent" style={{ marginTop: 16, borderTop: '2px solid rgba(59,130,246,0.3)' }}>
        <div className="card-header">
          <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: 'var(--info)' }}>📊</span> 详细指标
          </span>
        </div>
        <div className="card-body">
          <div className="param-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {Object.entries(m).map(([key, val]) => (
              <div key={key} className="param-item">
                <label className="param-label">{key}</label>
                <div style={{
                  background: 'var(--bg-card-hover)', padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)', fontSize: 13,
                  fontFamily: 'var(--font-mono)', border: '1px solid var(--border-light)',
                }}>
                  {typeof val === 'number'
                    ? (key.includes('pct') || key.includes('rate')
                      ? formatPct(val)
                      : key.includes('capital') || key.includes('equity')
                        ? formatAmount(val)
                        : formatNumber(val, 4))
                    : String(val)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {result.output_dir && (
        <div className="card card-gradient" style={{ marginTop: 8 }}>
          <div className="card-body" style={{ padding: '12px 16px', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span>💾</span> 结果已保存到: <code style={{ color: 'var(--text-primary)', background: 'var(--bg-input)', padding: '2px 8px' }}>{result.output_dir}</code>
          </div>
        </div>
      )}
    </>
  )
}
