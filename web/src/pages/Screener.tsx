import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '@/hooks/useApp'
import { useCachedStrategies } from '@/hooks/useCachedStrategies'
import { api } from '@/api/client'
import { MAX_DATE } from '@/utils/date'
import ScreenerParamsEditor from '@/components/ScreenerParamsEditor'
import StrategyParamsEditor from '@/components/StrategyParamsEditor'
import type { ScreenerInfo, ScreenResult, StrategyInfo } from '@/types'

function formatAmountStr(amount: number): string {
  if (amount >= 1e8) return (amount / 1e8).toFixed(2) + '\u4EBF'
  if (amount >= 1e4) return (amount / 1e4).toFixed(0) + '\u4E07'
  return String(amount)
}

function formatVolumeStr(vol: number): string {
  if (vol >= 1e6) return (vol / 1e6).toFixed(1) + 'M'
  if (vol >= 1e3) return (vol / 1e3).toFixed(0) + 'K'
  return String(vol)
}

export default function Screener() {
  const navigate = useNavigate()
  const { showToast, showLoading, hideLoading } = useApp()
  const { strategies } = useCachedStrategies()

  // Form state
  const [screeners, setScreeners] = useState<ScreenerInfo[]>([])
  const [screenerName, setScreenerName] = useState('momentum_screener')
  const [strategyName, setStrategyName] = useState('ma_cross')
  const [date, setDate] = useState('')
  const [topN, setTopN] = useState(20)
  const [screenerParams, setScreenerParams] = useState<Record<string, string>>({})
  const [strategyParams, setStrategyParams] = useState<Record<string, string>>({})

  // Result state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ScreenResult | null>(null)
  const [showBuyOnly, setShowBuyOnly] = useState(false)

  // Derived
  const selectedScreener = screeners.find(s => s.name === screenerName)
  const selectedStrategy = strategies.find(s => s.name === strategyName)
  const filteredResults = result
    ? (showBuyOnly ? result.results.filter(r => r.buy_signal !== null) : result.results)
    : []

  // Load screeners on mount
  useEffect(() => {
    api.getScreeners().then(data => {
      setScreeners(data.screeners)
      if (data.screeners.length > 0 && !data.screeners.find(s => s.name === screenerName)) {
        setScreenerName(data.screeners[0].name)
      }
    }).catch(() => {})
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Set default date to MAX_DATE
  useEffect(() => {
    if (!date) {
      setDate(MAX_DATE)
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // Search handler
  const handleSearch = useCallback(async () => {
    if (!date) {
      setError('\u8BF7\u9009\u62E9\u65E5\u671F')
      return
    }
    setLoading(true)
    setError(null)
    showLoading('\u6B63\u5728\u626B\u63CF\u5168\u5E02\u573A...')
    try {
      // Build params from form values (only include non-empty)
      const sp: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(screenerParams)) {
        if (v !== '' && v !== undefined) {
          const schema = selectedScreener?.param_schema?.[k]
          if (schema?.type === 'float') sp[k] = parseFloat(v)
          else if (schema?.type === 'int') sp[k] = parseInt(v, 10)
          else if (schema?.type === 'bool') sp[k] = v === 'true'
          else sp[k] = v
        }
      }
      const tp: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(strategyParams)) {
        if (v !== '' && v !== undefined) {
          const schema = selectedStrategy?.param_schema?.[k]
          if (schema?.type === 'float') tp[k] = parseFloat(v)
          else if (schema?.type === 'int') tp[k] = parseInt(v, 10)
          else if (schema?.type === 'bool') tp[k] = v === 'true'
          else tp[k] = v
        }
      }

      const res = await api.screen({
        screener: screenerName,
        strategy: strategyName,
        date,
        top_n: topN,
        screener_params: Object.keys(sp).length > 0 ? sp : undefined,
        strategy_params: Object.keys(tp).length > 0 ? tp : undefined,
      })
      setResult(res)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '\u9009\u80A1\u626B\u63CF\u5931\u8D25'
      setError(msg)
      showToast(msg, 'error')
    } finally {
      setLoading(false)
      hideLoading()
    }
  }, [date, screenerName, strategyName, topN, screenerParams, strategyParams, selectedScreener, selectedStrategy, showLoading, hideLoading, showToast])

  // Score color helper
  const scoreColor = (score: number) => {
    if (score >= 0.8) return 'var(--success)'
    if (score >= 0.6) return 'var(--warning)'
    return 'var(--text-muted)'
  }

  const hitRate = result && result.universe_size > 0
    ? ((result.with_buy_signal / result.universe_size) * 100).toFixed(2)
    : '0.00'

  return (
    <div className="page">
      {/* Hero */}
      <div className="page-hero">
        <h1 className="page-hero__title">{'\uD83D\uDCCA \u667A\u80FD\u9009\u80A1'}</h1>
        <p className="page-hero__desc">
          {'\u57FA\u4E8E\u9009\u80A1\u5668\u626B\u63CF + \u7B56\u7565\u4E70\u70B9\u786E\u8BA4\uFF0C\u53D1\u73B0\u5F53\u5929\u6700\u4F73\u5165\u573A\u673A\u4F1A'}
        </p>
      </div>

      {/* Form Card */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, alignItems: 'end' }}>
            {/* Screener selector */}
            <div>
              <label className="form-label">{'\u9009\u80A1\u5668'}</label>
              <select
                className="form-input"
                value={screenerName}
                onChange={e => { setScreenerName(e.target.value); setScreenerParams({}) }}
              >
                {screeners.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Strategy selector */}
            <div>
              <label className="form-label">{'\u4EA4\u6613\u7B56\u7565'}</label>
              <select
                className="form-input"
                value={strategyName}
                onChange={e => { setStrategyName(e.target.value); setStrategyParams({}) }}
              >
                {strategies.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </div>

            {/* Date picker */}
            <div>
              <label className="form-label">{'\u65E5\u671F'}</label>
              <input
                type="date"
                className="form-input"
                value={date}
                max={MAX_DATE}
                onChange={e => setDate(e.target.value)}
              />
            </div>

            {/* Top N */}
            <div>
              <label className="form-label">{'\u8FD4\u56DE\u6570\u91CF'}</label>
              <input
                type="number"
                className="form-input"
                value={topN}
                min={5}
                max={100}
                onChange={e => setTopN(parseInt(e.target.value, 10) || 20)}
              />
            </div>

            {/* Submit */}
            <div>
              <button className="btn btn-primary" onClick={handleSearch} disabled={loading} style={{ width: '100%' }}>
                {loading ? '\u626B\u63CF\u4E2D...' : '\uD83D\uDD0D \u5F00\u59CB\u9009\u80A1'}
              </button>
            </div>
          </div>

          {/* Parameter editors */}
          <ScreenerParamsEditor
            screener={selectedScreener}
            editParams={screenerParams}
            onChange={(k, v) => setScreenerParams(prev => ({ ...prev, [k]: v }))}
          />
          <StrategyParamsEditor
            strategy={selectedStrategy}
            editParams={strategyParams}
            onChange={(k, v) => setStrategyParams(prev => ({ ...prev, [k]: v }))}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="card" style={{ marginBottom: 24, borderLeft: '3px solid var(--danger)' }}>
          <div className="card-body" style={{ color: 'var(--danger)' }}>
            {'\u26A0\uFE0F'} {error}
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="skeleton" style={{ height: 80, borderRadius: 8 }} />
              ))}
            </div>
            <div className="skeleton" style={{ height: 400, borderRadius: 8 }} />
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          {/* Summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 24 }}>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{'\u626B\u63CF\u80A1\u7968'}</div>
                <div style={{ fontSize: 28, fontWeight: 700 }}>{result.universe_size.toLocaleString()}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{'\u5019\u9009\u80A1\u7968'}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--warning)' }}>{result.candidates}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{'\u6709\u4E70\u70B9'}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--success)' }}>{result.with_buy_signal}</div>
              </div>
            </div>
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{'\u547D\u4E2D\u7387'}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--info)' }}>{hitRate}%</div>
              </div>
            </div>
          </div>

          {/* Filter bar */}
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13 }}>
              <input
                type="checkbox"
                checked={showBuyOnly}
                onChange={e => setShowBuyOnly(e.target.checked)}
              />
              {'\u4EC5\u770B\u6709\u4E70\u70B9'}
            </label>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {'\u663E\u793A'} {filteredResults.length} / {result.results.length} {'\u53EA'}
            </span>
          </div>

          {/* Results table */}
          {filteredResults.length > 0 ? (
            <div className="card" style={{ overflow: 'auto' }}>
              <table className="table" style={{ minWidth: 900 }}>
                <thead>
                  <tr>
                    <th style={{ width: 40 }}>#</th>
                    <th style={{ width: 100 }}>{'\u4EE3\u7801'}</th>
                    <th style={{ width: 100 }}>{'\u540D\u79F0'}</th>
                    <th style={{ width: 80 }}>{'\u8BC4\u5206'}</th>
                    <th style={{ width: 140 }}>{'\u4FE1\u53F7\u6807\u7B7E'}</th>
                    <th style={{ width: 200 }}>{'\u56E0\u5B50\u660E\u7EC6'}</th>
                    <th style={{ width: 100 }}>{'\u4E70\u70B9'}</th>
                    <th style={{ width: 200 }}>{'\u5173\u952E\u6307\u6807'}</th>
                    <th style={{ width: 60 }}>{'\u64CD\u4F5C'}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((item, idx) => (
                    <tr key={item.symbol}>
                      <td>
                        {idx === 0 && item.buy_signal ? '\uD83E\uDD47' : idx === 1 && item.buy_signal ? '\uD83E\uDD48' : idx === 2 && item.buy_signal ? '\uD83E\uDD49' : idx + 1}
                      </td>
                      <td>
                        <button
                          className="btn-link"
                          style={{ fontWeight: 600, fontFamily: 'monospace' }}
                          onClick={() => navigate(`/analyze?symbol=${item.symbol}&strategy=${strategyName}`)}
                        >
                          {item.symbol}
                        </button>
                      </td>
                      <td style={{ fontSize: 13 }}>{item.name}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{
                            width: 60, height: 6, borderRadius: 3,
                            background: 'var(--border-light)', overflow: 'hidden',
                          }}>
                            <div style={{
                              width: `${(item.score * 100).toFixed(0)}%`,
                              height: '100%',
                              background: scoreColor(item.score),
                              borderRadius: 3,
                            }} />
                          </div>
                          <span style={{ fontSize: 13, fontWeight: 600, color: scoreColor(item.score) }}>
                            {item.score.toFixed(2)}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span style={{
                          background: 'var(--bg-secondary)',
                          color: 'var(--text-secondary)',
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 4,
                        }}>
                          {item.signal_tag}
                        </span>
                      </td>
                      <td>
                        {Object.keys(item.factor_breakdown).length > 0 ? (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)', cursor: 'help' }}
                            title={Object.entries(item.factor_breakdown).map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`).join('\n')}>
                            {Object.keys(item.factor_breakdown).length} {'\u4E2A\u56E0\u5B50'}
                          </span>
                        ) : (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{'\u2014'}</span>
                        )}
                      </td>
                      <td>
                        {item.buy_signal ? (
                          <div>
                            <span style={{
                              background: 'rgba(34,197,94,0.1)',
                              color: 'var(--success)',
                              fontSize: 11,
                              padding: '2px 8px',
                              borderRadius: 4,
                              marginRight: 4,
                            }}>
                              BUY {((item.buy_signal.strength ?? 0) * 100).toFixed(0)}%
                            </span>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                              title={item.buy_signal.reason}>
                              {item.buy_signal.reason}
                            </div>
                          </div>
                        ) : (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{'\u2014'}</span>
                        )}
                      </td>
                      <td style={{ fontSize: 11 }}>
                        <div>{'\u6536\u76D8'}: {item.key_metrics.close?.toFixed(2) ?? '\u2014'}</div>
                        <div>{'\u91CF'}: {item.key_metrics.volume ? formatVolumeStr(item.key_metrics.volume) : '\u2014'}</div>
                        <div>{'\u989D'}: {item.key_metrics.amount ? formatAmountStr(item.key_metrics.amount) : '\u2014'}</div>
                      </td>
                      <td>
                        <button
                          className="btn-link"
                          style={{ fontSize: 12 }}
                          onClick={() => navigate(`/analyze?symbol=${item.symbol}&strategy=${strategyName}`)}
                        >
                          {'\u67E5\u770B \u2192'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 40, marginBottom: 12 }}>{'\uD83D\uDCED'}</div>
                <p>{'\u5F53\u5929\u6CA1\u6709\u7B26\u5408\u6761\u4EF6\u7684\u80A1\u7968'}</p>
                <p style={{ fontSize: 12 }}>{'\u8BD5\u8BD5\u66F4\u6362\u9009\u80A1\u5668\u3001\u7B56\u7565\uFF0C\u6216\u8C03\u6574\u53C2\u6570'}</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
