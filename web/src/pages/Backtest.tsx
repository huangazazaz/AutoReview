import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '@/hooks/useApp'
import { useECharts } from '@/hooks/useECharts'
import { api } from '@/api/client'
import { PageHero, PageHeader, EmptyState } from '@/components/UI'
import StrategyParamsEditor from '@/components/StrategyParamsEditor'
import { formatNumber, formatPct, formatAmount, escapeHtml } from '@/utils/format'
import Select from 'react-select'
import CreatableSelect from 'react-select/creatable'
import type { StrategyInfo, BacktestSummary, BacktestResultItem, CachedStock, GroupInfo } from '@/types'

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const POS_COLOR = '#EF4444'
const NEG_COLOR = '#22C55E'

const PERIODS = [
  { value: '1M', label: '1个月' },
  { value: '3M', label: '3个月' },
  { value: '6M', label: '6个月' },
  { value: '1Y', label: '1年' },
  { value: '2Y', label: '2年' },
  { value: '5Y', label: '5年' },
]

function getPeriodDates(period: string): { start: string; end: string } {
  const now = new Date()
  const end = now.toISOString().slice(0, 10)
  const d = new Date()
  switch (period) {
    case '1M': d.setMonth(d.getMonth() - 1); break
    case '3M': d.setMonth(d.getMonth() - 3); break
    case '6M': d.setMonth(d.getMonth() - 6); break
    case '1Y': d.setFullYear(d.getFullYear() - 1); break
    case '2Y': d.setFullYear(d.getFullYear() - 2); break
    case '5Y': d.setFullYear(d.getFullYear() - 5); break
    default: return { start: '', end }
  }
  return { start: d.toISOString().slice(0, 10), end }
}

/* ------------------------------------------------------------------ */
/*  Medal SVGs                                                        */
/* ------------------------------------------------------------------ */

const GOLD_MEDAL_SVG =
  '<svg width="18" height="18"><circle cx="9" cy="9" r="8" stroke="#F59E0B" fill="rgba(245,158,11,0.15)"/><text x="9" y="9" textAnchor="middle" dominantBaseline="central" fontSize="10" fontWeight="700" fill="#F59E0B" stroke="none">1</text></svg>'

const SILVER_MEDAL_SVG =
  '<svg width="18" height="18"><circle cx="9" cy="9" r="8" stroke="#94A3B8" fill="rgba(148,163,184,0.15)"/><text x="9" y="9" textAnchor="middle" dominantBaseline="central" fontSize="10" fontWeight="700" fill="#94A3B8" stroke="none">2</text></svg>'

const BRONZE_MEDAL_SVG =
  '<svg width="18" height="18"><circle cx="9" cy="9" r="8" stroke="#D97706" fill="rgba(217,119,6,0.15)"/><text x="9" y="9" textAnchor="middle" dominantBaseline="central" fontSize="10" fontWeight="700" fill="#D97706" stroke="none">3</text></svg>'

function getMedalSvg(rank: number): string {
  if (rank === 1) return GOLD_MEDAL_SVG
  if (rank === 2) return SILVER_MEDAL_SVG
  if (rank === 3) return BRONZE_MEDAL_SVG
  return ''
}

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

const Backtest = () => {
  const navigate = useNavigate()
  const app = useApp()

  /* ---- ECharts hook ----------------------------------------------- */
  const { initChart, setOption } = useECharts()

  /* ---- refs ------------------------------------------------------ */
  const chartContainerRef = useRef<HTMLDivElement>(null)

  /* ---- form state ------------------------------------------------ */
  const [activeTab, setActiveTab] = useState<'symbols' | 'group'>('symbols')
  const [symbols, setSymbols] = useState('')
  const [selectedGroup, setSelectedGroup] = useState('')
  const [selectedStrategy, setSelectedStrategy] = useState('')
  const [selectedPeriod, setSelectedPeriod] = useState('1Y')
  const [selectedDatasource, setSelectedDatasource] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [strategyParams, setStrategyParams] = useState<Record<string, string>>({})
  const [showParamsEditor, setShowParamsEditor] = useState(false)

  /* ---- loaded data ----------------------------------------------- */
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [datasources, setDatasources] = useState<string[]>([])
  const [groups, setGroups] = useState<GroupInfo[]>([])
  const [cachedStocks, setCachedStocks] = useState<CachedStock[]>([])

  /* ---- results --------------------------------------------------- */
  const [summary, setSummary] = useState<BacktestSummary | null>(null)
  const [results, setResults] = useState<BacktestResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  /* ---- sorting --------------------------------------------------- */
  const [sortKey, setSortKey] = useState<string>('return_pct')
  const [sortAsc, setSortAsc] = useState(false)

  /* ================================================================ */
  /*  Data loading on mount                                           */
  /* ================================================================ */

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const [stratRes, dsRes, grpRes, cachedRes] = await Promise.all([
          api.getStrategies(),
          api.getDatasources(),
          api.getGroups(),
          api.getCachedStocks(),
        ])
        if (cancelled) return
        setStrategies(stratRes.strategies ?? [])
        setDatasources(dsRes.datasources ?? [])
        setGroups(grpRes.groups ?? [])
        setCachedStocks(cachedRes.symbols ?? [])
      } catch (err) {
        if (!cancelled) console.error('Failed to load initial data:', err)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  /* ---- Set initial dates from default period (1Y) ----------------- */
  useEffect(() => {
    const { start, end } = getPeriodDates('1Y')
    setStartDate(start)
    setEndDate(end)
  }, [])

  /* ================================================================ */
  /*  Add cached stock helpers                                        */
  /* ================================================================ */

  const symbolsArray = useMemo(
    () =>
      symbols
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
    [symbols],
  )

  const handlePeriodChange = useCallback((value: string) => {
    setSelectedPeriod(value)
    const { start, end } = getPeriodDates(value)
    setStartDate(start)
    setEndDate(end)
  }, [])

  /* ================================================================ */
  /*  Find selected strategy object (for StrategyParamsEditor)        */
  /* ================================================================ */

  const selectedStrategyObj = useMemo<StrategyInfo | undefined>(() => {
    if (!selectedStrategy) return undefined
    return strategies.find((s) => s.name === selectedStrategy)
  }, [selectedStrategy, strategies])

  /* ================================================================ */
  /*  Submit                                                          */
  /* ================================================================ */

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError('')

      // --- validation -------------------------------------------------
      if (activeTab === 'symbols') {
        if (!symbols.trim()) {
          setError('请输入股票代码')
          return
        }
      } else {
        if (!selectedGroup) {
          setError('请选择分组')
          return
        }
      }

      if (!selectedStrategy) {
        setError('请选择策略')
        return
      }

      // --- build payload ----------------------------------------------
      const symbolList =
        activeTab === 'symbols'
          ? symbols
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          : []

      const payload: Record<string, unknown> = {
        strategy: selectedStrategy,
        period: selectedPeriod || undefined,
        datasource: selectedDatasource || undefined,
        start: startDate || undefined,
        end: endDate || undefined,
        strategy_params:
          Object.keys(strategyParams).length > 0 ? strategyParams : undefined,
      }

      if (activeTab === 'symbols') {
        payload.symbols = symbolList.join(',')
      } else {
        payload.group = selectedGroup
      }

      // --- call -------------------------------------------------------
      setLoading(true)
      try {
        const response = await api.backtest(payload as Parameters<typeof api.backtest>[0])
        // api.backtest() returns BacktestSummary directly
        setSummary(response)
        setResults(response.results ?? [])
        setSortKey('return_pct')
        setSortAsc(false)
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : String(err ?? '回测失败')
        setError(msg)
        setSummary(null)
        setResults([])
      } finally {
        setLoading(false)
      }
    },
    [
      activeTab,
      symbols,
      selectedGroup,
      selectedStrategy,
      selectedPeriod,
      selectedDatasource,
      startDate,
      endDate,
      strategyParams,
    ],
  )

  /* ================================================================ */
  /*  ECharts – horizontal bar chart  (via useECharts hook)           */
  /* ================================================================ */

  useEffect(() => {
    const container = chartContainerRef.current
    if (!container || results.length === 0) return

    initChart(container)

    // Sort by return descending so the chart reads top → bottom
    const sorted = [...results].sort(
      (a, b) => (b.return_pct ?? 0) - (a.return_pct ?? 0),
    )
    const names = sorted.map((r) => r.symbol)
    const values = sorted.map((r) => r.return_pct ?? 0)

    const option: Parameters<typeof setOption>[0] = {
      backgroundColor: '#1E293B',

      title: {
        text: '收益率对比',
        subtext: '红涨绿跌 · 色盲友好设计 · 实心为正收益，斜纹为负收益',
        left: 'center',
        textStyle: { color: '#E2E8F0', fontSize: 16 },
        subtextStyle: { color: '#94A3B8', fontSize: 12 },
      },

      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: unknown) => {
          const arr = Array.isArray(params) ? params : [params]
          const p = arr[0] as Record<string, unknown> | undefined
          if (!p) return ''
          const safeName = escapeHtml(String(p.name ?? ''))
          return `${safeName}<br/>收益率: ${Number(p.value ?? 0).toFixed(2)}%`
        },
      },

      grid: {
        left: '3%',
        right: '9%',
        top: '18%',
        bottom: '3%',
        containLabel: true,
      },

      xAxis: {
        type: 'value',
        axisLabel: {
          color: '#94A3B8',
          formatter: '{value}%',
        },
        splitLine: {
          lineStyle: { color: '#334155' },
        },
      },

      yAxis: {
        type: 'category',
        data: names,
        axisLabel: {
          color: '#E2E8F0',
          fontSize: 12,
        },
        axisLine: { lineStyle: { color: '#475569' } },
        axisTick: { show: false },
      },

      series: [
        {
          type: 'bar',
          data: values.map((val) => ({
            value: val,
            itemStyle: {
              color: val >= 0 ? POS_COLOR : NEG_COLOR,
              ...(val < 0
                ? {
                    decal: {
                      symbol: 'rect',
                      symbolSize: 0.6,
                      dashArrayX: [2, 2],
                      dashArrayY: [2, 2],
                      rotation: Math.PI / 4,
                      color: 'rgba(255,255,255,0.12)',
                    },
                  }
                : {}),
            },
          })),
          label: {
            show: true,
            position: 'right',
            color: '#E2E8F0',
            fontSize: 11,
            formatter: (params: unknown) =>
              `${(Number((params as Record<string, unknown>).value ?? 0)).toFixed(2)}%`,
          },
          barMaxWidth: 30,
        },
      ],

      aria: {
        enabled: true,
        decal: { show: true },
        description:
          '批量回测收益率对比图。红色表示正收益，绿色表示负收益。负收益条形使用斜纹图案以便色盲用户区分。',
      },
    }

    setOption(option)
    // cleanup (resize listener + dispose) is handled by useECharts hook
  }, [results, initChart, setOption])

  /* ================================================================ */
  /*  Sorting helpers                                                 */
  /* ================================================================ */

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        setSortAsc((prev) => !prev)
      } else {
        setSortKey(key)
        setSortAsc(false)
      }
    },
    [sortKey],
  )

  const getSortIndicator = (key: string): string => {
    if (sortKey !== key) return ''
    return sortAsc ? ' ▲' : ' ▼'
  }

  const getAriaSort = (
    key: string,
  ): 'none' | 'ascending' | 'descending' => {
    if (sortKey !== key) return 'none'
    return sortAsc ? 'ascending' : 'descending'
  }

  /* ---- sorted results -------------------------------------------- */

  const sortedResults = useMemo(() => {
    const copy = [...results]
    copy.sort((a, b) => {
      if (sortKey === 'rank') {
        // rank is determined by return_pct descending by default
        return sortAsc
          ? (a.return_pct ?? 0) - (b.return_pct ?? 0)
          : (b.return_pct ?? 0) - (a.return_pct ?? 0)
      }
      const aVal = a[sortKey as keyof BacktestResultItem] ?? 0
      const bVal = b[sortKey as keyof BacktestResultItem] ?? 0
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortAsc ? aVal - bVal : bVal - aVal
      }
      const sa = String(aVal)
      const sb = String(bVal)
      return sortAsc ? sa.localeCompare(sb) : sb.localeCompare(sa)
    })
    return copy
  }, [results, sortKey, sortAsc])

  /* ================================================================ */
  /*  Row click → /analyze                                            */
  /* ================================================================ */

  const handleRowClick = useCallback(
    (symbol: string) => {
      setTimeout(() => {
        navigate(`/analyze?symbol=${encodeURIComponent(symbol)}`)
      }, 0)
    },
    [navigate],
  )

  /* ================================================================ */
  /*  Derived                                                         */
  /* ================================================================ */

  const hasResults = summary !== null && results.length > 0
  const chartHeight = Math.max(300, results.length * 40 + 80)

  /* ================================================================ */
  /*  Render                                                          */
  /* ================================================================ */

  return (
    <div className="backtest-page">
      {/* ---- hero --------------------------------------------------- */}
      <PageHero>
        <PageHeader
          title="批量回测"
          subtitle="同时对多只股票执行策略回测，快速对比收益表现"
        />
      </PageHero>

      {/* ============================================================ */}
      {/*  Configuration form                                           */}
      {/* ============================================================ */}

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">回测配置</h2>
        </div>

        <div className="card-body">
          <form onSubmit={handleSubmit} noValidate>
            {/* ---- tabs --------------------------------------------- */}
            <div className="tabs" role="tablist">
              <button
                type="button"
                className={`tab ${activeTab === 'symbols' ? 'active' : 'inactive'}`}
                role="tab"
                aria-selected={activeTab === 'symbols'}
                onClick={() => setActiveTab('symbols')}
              >
                按代码
              </button>
              <button
                type="button"
                className={`tab ${activeTab === 'group' ? 'active' : 'inactive'}`}
                role="tab"
                aria-selected={activeTab === 'group'}
                onClick={() => setActiveTab('group')}
              >
                按分组
              </button>
            </div>

            {/* ====================================================== */}
            {/*  Symbols mode                                           */}
            {/* ====================================================== */}

            {activeTab === 'symbols' && (
              <>
                <div className="form-row">
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label" htmlFor="symbols-input">
                      股票
                    </label>
                    <CreatableSelect
                      id="symbols-input"
                      isMulti
                      placeholder="输入代码或名称搜索股票，支持多选…"
                      options={cachedStocks.map(s => ({
                        value: s.symbol,
                        label: `${s.symbol}${s.name ? ` - ${s.name}` : ''}`
                      }))}
                      value={symbolsArray.map(code => {
                        const s = cachedStocks.find(c => c.symbol === code)
                        return s
                          ? { value: s.symbol, label: `${s.symbol}${s.name ? ` - ${s.name}` : ''}` }
                          : { value: code, label: code }
                      })}
                      onChange={(items) => {
                        const codes = items.map(i => i.value)
                        setSymbols(codes.join(', '))
                      }}
                      onCreateOption={(input) => {
                        const code = input.toUpperCase()
                        if (!symbolsArray.includes(code)) {
                          setSymbols(symbols ? `${symbols}, ${code}` : code)
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
                      noOptionsMessage={() => '未找到，输入代码后按回车添加'}
                      formatCreateLabel={(v) => `添加 "${v.toUpperCase()}"`}
                    />
                  </div>
                </div>
              </>
            )}

            {/* ====================================================== */}
            {/*  Group mode                                             */}
            {/* ====================================================== */}

            {activeTab === 'group' && (
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label" htmlFor="group-select">
                    选择分组
                  </label>
                  <Select
                    id="group-select"
                    placeholder="选择分组…"
                    options={groups.map(g => ({ value: g.id, label: g.name || g.id }))}
                    value={selectedGroup ? { value: selectedGroup, label: groups.find(g => g.id === selectedGroup)?.name || selectedGroup } : null}
                    onChange={(o) => setSelectedGroup(o?.value || '')}
                    isClearable
                    isLoading={groups.length === 0}
                    loadingMessage={() => '正在加载…'}
                    menuPortalTarget={document.body}
                    className="react-select"
                    classNamePrefix="rs"
                  />
                </div>
              </div>
            )}

            {/* ====================================================== */}
            {/*  Common fields                                          */}
            {/* ====================================================== */}
 
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="strategy-select">
                  选择策略
                </label>
                <Select
                  id="strategy-select"
                  placeholder="选择策略…"
                  options={strategies.map(s => ({ value: s.name, label: s.name }))}
                  value={selectedStrategy ? { value: selectedStrategy, label: selectedStrategy } : null}
                  onChange={(o) => setSelectedStrategy(o?.value || '')}
                  isClearable
                  isLoading={strategies.length === 0}
                  loadingMessage={() => '正在加载…'}
                  menuPortalTarget={document.body}
                  className="react-select"
                  classNamePrefix="rs"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="period-select">
                  回测周期
                </label>
                <Select
                  id="period-select"
                  placeholder="默认"
                  options={PERIODS}
                  value={PERIODS.find(p => p.value === selectedPeriod) || null}
                  onChange={(o) => handlePeriodChange(o?.value || '1Y')}
                  menuPortalTarget={document.body}
                  className="react-select"
                  classNamePrefix="rs"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="datasource-select">
                  数据源
                </label>
                <Select
                  id="datasource-select"
                  placeholder="默认"
                  options={datasources.map(ds => ({ value: ds, label: ds }))}
                  value={selectedDatasource ? { value: selectedDatasource, label: selectedDatasource } : null}
                  onChange={(o) => setSelectedDatasource(o?.value || '')}
                  isLoading={datasources.length === 0}
                  loadingMessage={() => '正在加载…'}
                  menuPortalTarget={document.body}
                  className="react-select"
                  classNamePrefix="rs"
                />
              </div>
            </div>

            {/* ---- dates -------------------------------------------- */}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="start-date">
                  开始日期
                </label>
                <input
                  id="start-date"
                  type="date"
                  className="form-input date-input"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="end-date">
                  结束日期
                </label>
                <input
                  id="end-date"
                  type="date"
                  className="form-input date-input"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>

            {/* ---- strategy params toggle --------------------------- */}
            <div className="form-row">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowParamsEditor((prev) => !prev)}
                aria-expanded={showParamsEditor}
              >
                {showParamsEditor ? '隐藏策略参数' : '策略参数设置'}
              </button>
            </div>

            {showParamsEditor && (
              <div className="form-row">
                <StrategyParamsEditor
                  strategy={selectedStrategyObj}
                  editParams={strategyParams}
                  onChange={(key: string, value: string) => {
                    setStrategyParams((prev) => ({ ...prev, [key]: value }))
                  }}
                />
              </div>
            )}

            {/* ---- error -------------------------------------------- */}
            {error && (
              <div className="form-row">
                <p style={{ color: POS_COLOR, margin: 0 }} role="alert">
                  {error}
                </p>
              </div>
            )}

            {/* ---- submit ------------------------------------------- */}
            <div className="form-row">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
              >
                {loading ? '回测中…' : '开始批量回测'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* ============================================================ */}
      {/*  Results section                                              */}
      {/* ============================================================ */}

      {hasResults && summary && (
        <div className="card card-accent" style={{ marginTop: '24px' }}>
          <div className="card-header">
            <h2 className="card-title">回测结果</h2>
          </div>

          <div className="card-body">
            {/* ---- summary stats grid ------------------------------- */}
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">股票总数</div>
                <div className="stat-value">
                  {summary.total ?? results.length}
                </div>
                <div className="stat-sub">
                  正收益占比:{' '}
                  {formatPct(
                    (summary.positive_count ?? 0) /
                      Math.max(summary.total ?? results.length, 1),
                  )}
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">成功 / 失败</div>
                <div className="stat-value">
                  <span className="stat-positive">
                    {summary.success ?? 0}
                  </span>
                  {' / '}
                  <span className="stat-negative">
                    {summary.failed ?? 0}
                  </span>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">平均收益率</div>
                <div
                  className={`stat-value ${
                    (summary.avg_return_pct ?? 0) >= 0
                      ? 'stat-positive'
                      : 'stat-negative'
                  }`}
                >
                  {formatPct(summary.avg_return_pct ?? 0)}
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">最佳</div>
                <div className="stat-value stat-positive">
                  {summary.best_symbol ? `${summary.best_symbol} ` : ''}
                  {formatPct(summary.best_return ?? 0)}
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-label">最差</div>
                <div className="stat-value stat-negative">
                  {summary.worst_symbol ? `${summary.worst_symbol} ` : ''}
                  {formatPct(summary.worst_return ?? 0)}
                </div>
              </div>
            </div>

            {/* ---- chart + table side-by-side ----------------------- */}
            <div
              style={{
                display: 'flex',
                gap: '24px',
                marginTop: '24px',
                flexWrap: 'wrap',
              }}
            >
              {/* ==================================================== */}
              {/*  Bar chart                                            */}
              {/* ==================================================== */}

              <div style={{ flex: '1 1 55%', minWidth: '400px' }}>
                <div
                  ref={chartContainerRef}
                  className="chart-container"
                  style={{
                    width: '100%',
                    height: `${chartHeight}px`,
                  }}
                  role="img"
                  aria-label="批量回测收益率对比图。红色表示正收益，绿色带斜纹表示负收益。"
                />

                <div className="sr-only">
                  屏幕阅读器摘要：此图展示了 {results.length}{' '}
                  只股票的批量回测收益率对比。
                  {sortedResults.length > 0 &&
                    `最高收益为 ${sortedResults[0].symbol} ${(sortedResults[0].return_pct ?? 0).toFixed(2)}%，` +
                      `最低收益为 ${sortedResults[sortedResults.length - 1].symbol} ${(sortedResults[sortedResults.length - 1].return_pct ?? 0).toFixed(2)}%。`}
                </div>
              </div>

              {/* ==================================================== */}
              {/*  Rankings table                                       */}
              {/* ==================================================== */}

              <div style={{ flex: '1 1 40%', minWidth: '350px' }}>
                <div className="table-container">
                  <table
                    style={{ width: '100%', borderCollapse: 'collapse' }}
                  >
                    <thead>
                      <tr>
                        <th
                          className={`clickable${sortKey === 'rank' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('rank')}
                          onClick={() => handleSort('rank')}
                          style={{ cursor: 'pointer', width: '40px' }}
                        >
                          #{getSortIndicator('rank')}
                        </th>
                        <th
                          className={`clickable${sortKey === 'symbol' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('symbol')}
                          onClick={() => handleSort('symbol')}
                          style={{ cursor: 'pointer' }}
                        >
                          股票{getSortIndicator('symbol')}
                        </th>
                        <th
                          className={`clickable${sortKey === 'return_pct' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('return_pct')}
                          onClick={() => handleSort('return_pct')}
                          style={{ cursor: 'pointer' }}
                        >
                          收益率{getSortIndicator('return_pct')}
                        </th>
                        <th
                          className={`clickable${sortKey === 'max_drawdown_pct' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('max_drawdown_pct')}
                          onClick={() => handleSort('max_drawdown_pct')}
                          style={{ cursor: 'pointer' }}
                        >
                          最大回撤{getSortIndicator('max_drawdown_pct')}
                        </th>
                        <th
                          className={`clickable${sortKey === 'sharpe' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('sharpe')}
                          onClick={() => handleSort('sharpe')}
                          style={{ cursor: 'pointer' }}
                        >
                          夏普{getSortIndicator('sharpe')}
                        </th>
                        <th
                          className={`clickable${sortKey === 'win_rate' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('win_rate')}
                          onClick={() => handleSort('win_rate')}
                          style={{ cursor: 'pointer' }}
                        >
                          胜率{getSortIndicator('win_rate')}
                        </th>
                        <th
                          className={`clickable${sortKey === 'trades' ? ' sorted' : ''}`}
                          aria-sort={getAriaSort('trades')}
                          onClick={() => handleSort('trades')}
                          style={{ cursor: 'pointer' }}
                        >
                          交易{getSortIndicator('trades')}
                        </th>
                      </tr>
                    </thead>

                    <tbody>
                      {sortedResults.map((result, index) => {
                        const rank = index + 1
                        const sym = result.symbol
                        const medalHtml = getMedalSvg(rank)

                        return (
                          <tr
                            key={sym || index}
                            className="clickable"
                            onClick={() => handleRowClick(sym)}
                            style={{ cursor: 'pointer' }}
                          >
                            <td style={{ textAlign: 'center' }}>
                              {medalHtml ? (
                                <span
                                  dangerouslySetInnerHTML={{
                                    __html: medalHtml,
                                  }}
                                />
                              ) : (
                                <span className="badge-outline">
                                  {rank}
                                </span>
                              )}
                            </td>
                            <td>
                              <strong>{sym}</strong>
                            </td>
                            <td
                              className={
                                (result.return_pct ?? 0) >= 0
                                  ? 'stat-positive'
                                  : 'stat-negative'
                              }
                            >
                              {formatPct(result.return_pct ?? 0)}
                            </td>
                            <td>
                              {formatPct(result.max_drawdown_pct ?? 0)}
                            </td>
                            <td>{formatNumber(result.sharpe ?? 0, 2)}</td>
                            <td>{formatPct(result.win_rate ?? 0)}</td>
                            <td>{formatNumber(result.trades ?? 0)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/*  Empty state (no results yet)                                 */}
      {/* ============================================================ */}

      {!hasResults && !loading && (
        <div style={{ marginTop: '24px' }}>
          <EmptyState
            icon={<span>📊</span>}
            title="尚未开始回测"
            desc="配置回测参数后，点击「开始批量回测」查看结果"
          />
        </div>
      )}
    </div>
  )
}

export default Backtest
