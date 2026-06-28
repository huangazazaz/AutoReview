import { useState, useEffect, useCallback } from 'react'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHeader } from '@/components/UI'
import DateRangeInput from '@/components/DateRangeInput'
import { formatNumber, formatPct, formatAmount } from '@/utils/format'
import type { StrategyInfo, PortfolioBacktestResponse } from '@/types'

export default function Portfolio() {
  const { showToast, showLoading: showGlobalLoading, hideLoading } = useApp()

  const [screener, setScreener] = useState('momentum_screener')
  const [strategy, setStrategy] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [symbols, setSymbols] = useState('all')
  const [submitting, setSubmitting] = useState(false)

  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [result, setResult] = useState<PortfolioBacktestResponse | null>(null)

  // Strategy params
  const [paramSchema, setParamSchema] = useState<Record<string, { default?: unknown; type?: string }>>({})
  const [editParams, setEditParams] = useState<Record<string, string>>({})
  const [paramsExpanded, setParamsExpanded] = useState(false)

  useEffect(() => {
    api.getStrategies().then(d => setStrategies(d.strategies))
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
      symbols,
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
  }, [screener, strategy, startDate, endDate, symbols, editParams, paramSchema])

  const hasParams = strategy && Object.keys(paramSchema).length > 0

  return (
    <>
      <PageHeader title="组合回测" subtitle="单账户多持仓 + 股票筛选 + 策略择时，模拟真实账户收益" />

      <div className="card">
        <div className="card-header"><span className="card-title">回测参数</span></div>
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
              <label className="form-label" htmlFor="pf-strategy">择时策略 <span style={{ fontWeight: 400, color: 'var(--text-muted)', fontSize: 11 }}>(可选)</span></label>
              <select className="form-select" id="pf-strategy" value={strategy} onChange={e => setStrategy(e.target.value)}>
                <option value="">— 纯 Screener 模式 —</option>
                {strategies.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="pf-symbols">股票池</label>
              <select className="form-select" id="pf-symbols" value={symbols} onChange={e => setSymbols(e.target.value)}>
                <option value="all">全市场 (all)</option>
                <option value="000001,000002,600000,600036,601318">测试集 (5只)</option>
              </select>
            </div>
            <div className="form-group" style={{ minWidth: 280 }}>
              <label className="form-label">日期范围</label>
              <DateRangeInput startDate={startDate} endDate={endDate}
                onChange={(s, e) => { setStartDate(s); setEndDate(e) }} />
            </div>
            <div className="form-group" style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button className="btn btn-primary" style={{ width: '100%' }} onClick={submit} disabled={submitting}>
                {submitting ? '⏳ 回测中...' : '🚀 开始组合回测'}
              </button>
            </div>
          </div>

          {hasParams && (
            <div className="params-section">
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
    return <div className="card"><div className="card-body"><div className="empty-state"><p>无回测结果</p></div></div></div></div>
  }

  const isProfitable = m.total_return_pct >= 0
  const mode = strategy ? `${screener} + ${strategy}` : `${screener} (纯筛选)`

  return (
    <>
      <div className="stats-grid" style={{ marginTop: 16 }}>
        <div className="stat-card">
          <div className="stat-label">回测模式</div>
          <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>{mode}</div>
          <div className="stat-sub">{result.trade_count} 笔交易</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">初始资金 → 最终权益</div>
          <div className="stat-value stat-neutral" style={{ fontSize: 18 }}>
            {formatAmount(m.initial_capital)} → {formatAmount(m.final_equity)}
          </div>
          <div className="stat-sub" style={{ color: isProfitable ? 'var(--buy)' : 'var(--sell)' }}>
            {isProfitable ? '盈利' : '亏损'} {formatAmount(Math.abs(m.final_equity - m.initial_capital))}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-label">总收益率</div>
          <div className={'stat-value ' + (isProfitable ? 'stat-positive' : 'stat-negative')}>
            {formatPct(m.total_return_pct)}
          </div>
          <div className="stat-sub">最大回撤 {formatPct(m.max_drawdown_pct)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">胜率 / 夏普比率</div>
          <div className="stat-value stat-neutral" style={{ fontSize: 20 }}>
            {formatPct(m.win_rate)} <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>/</span> {formatNumber(m.sharpe_ratio, 3)}
          </div>
          <div className="stat-sub">{m.total_trades} 笔交易</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header"><span className="card-title">详细指标</span></div>
        <div className="card-body">
          <div className="param-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {Object.entries(m).map(([key, val]) => (
              <div key={key} className="param-item">
                <label className="param-label">{key}</label>
                <div className="form-input" style={{ background: 'var(--bg-card-hover)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', fontSize: 13 }}>
                  {typeof val === 'number' ? (key.includes('pct') || key.includes('rate') ? formatPct(val) : key.includes('capital') || key.includes('equity') ? formatAmount(val) : formatNumber(val, 4)) : String(val)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {result.output_dir && (
        <div className="card" style={{ marginTop: 8 }}>
          <div className="card-body" style={{ padding: '12px 16px', fontSize: 13, color: 'var(--text-muted)' }}>
            💾 结果已保存到: <code style={{ color: 'var(--text-primary)' }}>{result.output_dir}</code>
          </div>
        </div>
      )}
    </>
  )
}
