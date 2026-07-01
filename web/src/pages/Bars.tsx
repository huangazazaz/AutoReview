import { useState, useEffect, useCallback, useRef } from 'react'
import CreatableSelect from 'react-select/creatable'
import { useECharts } from '@/hooks/useECharts'
import { api } from '@/api/client'
import { PageHero, PageHeader, EmptyState } from '@/components/UI'
import { formatNumber, formatPct, formatAmount, formatVolume, escapeHtml } from '@/utils/format'
import type { BarsResponse, Bar } from '@/types'
import type { EChartsOption } from 'echarts'

// ── Types ──────────────────────────────────────────────────────────────────

interface CachedStock {
  symbol: string
  name: string
}

interface BarStats {
  label0: string
  val0: string
  sub0: string
  label1: string
  val1: string
  sub1: string
  label2: string
  val2: string
  sub2: string
  label3: string
  val3: string
  sub3: string
  selectedDate: string | null
  className0: string
  className1: string
  className2: string
  className3: string
}

// ── Helpers ────────────────────────────────────────────────────────────────

function computeStats(bars: Bar[], selectedIdx: number | null): BarStats | null {
  if (!bars || bars.length === 0) return null

  const latest = bars[bars.length - 1]
  const prev = bars.length > 1 ? bars[bars.length - 2] : null
  const periodHigh = Math.max(...bars.map((b) => b.high))
  const periodLow = Math.min(...bars.map((b) => b.low))
  const totalVolume = bars.reduce((s, b) => s + b.volume, 0)
  const totalAmount = bars.reduce((s, b) => s + (b.amount || 0), 0)

  // ── Selected bar stats ─────────────────────────────────────────────
  if (selectedIdx !== null && selectedIdx >= 0 && selectedIdx < bars.length) {
    const bar = bars[selectedIdx]
    const prevBar = selectedIdx > 0 ? bars[selectedIdx - 1] : null
    const chg = prevBar ? bar.close - prevBar.close : 0
    const chgPct = prevBar ? (chg / prevBar.close) * 100 : 0
    const amp = bar.low !== 0 ? ((bar.high - bar.low) / bar.low) * 100 : 0

    return {
      label0: '选中日收盘',
      val0: formatNumber(bar.close),
      sub0: `${chg >= 0 ? '+' : ''}${formatNumber(chg)} (${formatPct(chgPct)})`,
      label1: '当日最高/最低',
      val1: `${formatNumber(bar.high)} / ${formatNumber(bar.low)}`,
      sub1: `振幅 ${formatPct(amp)}`,
      label2: '开盘/最高/最低',
      val2: `${formatNumber(bar.open)} / ${formatNumber(bar.high)} / ${formatNumber(bar.low)}`,
      sub2: `日期: ${bar.date}`,
      label3: '成交量/成交额',
      val3: `${formatVolume(bar.volume)} / ${formatAmount(bar.amount)}`,
      sub3: `日期: ${bar.date}`,
      selectedDate: bar.date,
      className0: chg >= 0 ? 'stat-positive' : 'stat-negative',
      className1: 'stat-neutral',
      className2: 'stat-neutral',
      className3: 'stat-neutral',
    }
  }

  // ── Overall stats ──────────────────────────────────────────────────
  const chg = prev ? latest.close - prev.close : 0
  const chgPct = prev ? (chg / prev.close) * 100 : 0
  const amp = periodLow !== 0 ? ((periodHigh - periodLow) / periodLow) * 100 : 0

  return {
    label0: '最新收盘',
    val0: formatNumber(latest.close),
    sub0: `${chg >= 0 ? '+' : ''}${formatNumber(chg)} (${formatPct(chgPct)})`,
    label1: '期间最高/最低',
    val1: `${formatNumber(periodHigh)} / ${formatNumber(periodLow)}`,
    sub1: `振幅 ${formatPct(amp)}`,
    label2: '开盘/最高/最低',
    val2: `${formatNumber(latest.open)} / ${formatNumber(latest.high)} / ${formatNumber(latest.low)}`,
    sub2: `最新交易日: ${latest.date}`,
    label3: '成交量/成交额',
    val3: `${formatVolume(totalVolume)} / ${formatAmount(totalAmount)}`,
    sub3: `共 ${bars.length} 条数据`,
    selectedDate: null,
    className0: chg >= 0 ? 'stat-positive' : 'stat-negative',
    className1: 'stat-neutral',
    className2: 'stat-neutral',
    className3: 'stat-neutral',
  }
}

// ── Component ──────────────────────────────────────────────────────────────

function Bars() {
  // Hooks
  const { initChart, setOption, getChart } = useECharts()

  // Refs
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const selectedIdxRef = useRef<number | null>(null)
  const tableBodyRef = useRef<HTMLTableSectionElement>(null)

  // Form state
  const [symbol, setSymbol] = useState('')
  const [period, setPeriod] = useState('20d')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Data state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [bars, setBars] = useState<Bar[]>([])
  const [stockName, setStockName] = useState('')
  const [responseSymbol, setResponseSymbol] = useState('')

  // UI state
  const [cachedStocks, setCachedStocks] = useState<CachedStock[]>([])
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)
  const [chartSummary, setChartSummary] = useState('')

  // ── Load cached stocks for autocomplete ──────────────────────────────
  useEffect(() => {
    const loadStocks = async () => {
      try {
        const result = await api.getCachedStocks()
        if (result?.symbols?.length) {
          setCachedStocks(result.symbols)
        }
      } catch {
        // Autocomplete will just be empty — non-critical
      }
    }
    loadStocks()
  }, [])

  // ── Keep selectedIdxRef in sync ────────────────────────────────────
  useEffect(() => {
    selectedIdxRef.current = selectedIdx
  }, [selectedIdx])

  // ── Selection helpers ──────────────────────────────────────────────
  const updateStatsPanel = useCallback((idx: number | null) => {
    setSelectedIdx(idx)
  }, [])

  const resetSelection = useCallback(() => {
    updateStatsPanel(null)
  }, [updateStatsPanel])

  // ── Submit handler ──────────────────────────────────────────────────
  const handleSubmit = useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault()
      const trimmed = symbol.trim()
      if (!trimmed) return

      setLoading(true)
      setError(null)
      setSelectedIdx(null)
      setBars([])

      try {
        const params: any = { symbol: trimmed.toUpperCase() }
        if (startDate && endDate) {
          params.start = startDate
          params.end = endDate
        } else {
          params.period = period
        }

        const result: BarsResponse = await api.getBars(params)

        if (result?.bars?.length) {
          setBars(result.bars)
          setStockName(result.stock_name || trimmed.toUpperCase())
          setResponseSymbol(result.symbol || trimmed.toUpperCase())
        } else {
          setError('未查询到数据，请检查股票代码和日期范围')
        }
      } catch (err: any) {
        setError(err?.message || '查询失败，请稍后重试')
      } finally {
        setLoading(false)
      }
    },
    [symbol, period, startDate, endDate],
  )

  // ── Chart initialization / update ───────────────────────────────────
  useEffect(() => {
    if (!chartContainerRef.current || bars.length === 0) return

    // Initialize chart via hook (disposes any previous instance internally)
    initChart(chartContainerRef.current)

    // ── Build data arrays ─────────────────────────────────────────
    const dates = bars.map((b) => b.date)

    const ohlcData: any[] = bars.map((b) => ({
      value: [b.open, b.close, b.low, b.high],
      itemStyle:
        b.close > b.open
          ? { color: '#EF4444', borderColor: '#EF4444', borderWidth: 1 }
          : { color: 'transparent', borderColor: '#22C55E', borderWidth: 2 },
    }))

    const volumeData: any[] = bars.map((b) => ({
      value: b.volume,
      itemStyle: {
        color: b.close >= b.open ? '#EF4444' : '#22C55E',
      },
    }))

    const displaySymbol = responseSymbol || symbol.toUpperCase()
    const displayName = stockName || displaySymbol

    // ── ECharts option ────────────────────────────────────────────
    const option: EChartsOption = {
      title: {
        text: `${displaySymbol} ${displayName} 日线图`,
        subtext: '色觉友好设计：红涨绿跌 · 实心阳线 / 空心阴线 · 点击 K 线查看详情',
        left: 'center',
        textStyle: { color: '#E2E8F0', fontSize: 14 },
        subtextStyle: { color: '#94A3B8', fontSize: 11 },
      },
      backgroundColor: '#1E293B',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(30, 41, 59, 0.95)',
        borderColor: '#475569',
        textStyle: { color: '#E2E8F0', fontSize: 12 },
        formatter: (params: any) => {
          if (!params || params.length === 0) return ''
          const k = params.find((p: any) => p.seriesName === 'K线')
          const v = params.find((p: any) => p.seriesName === '成交量')
          if (!k) return ''
          const raw = k.data?.value ?? k.value ?? [0, 0, 0, 0]
          const [open, close, low, high] = raw
          const vol = v?.data?.value ?? v?.value ?? 0
          const chg = close - open
          const chgPct = open !== 0 ? ((close - open) / open) * 100 : 0
          const up = chg >= 0
          const color = up ? '#EF4444' : '#22C55E'
          return `
            <div style="font-size:13px;line-height:1.8">
              <strong>${escapeHtml(String(k.axisValue))}</strong><br/>
              开盘: ${formatNumber(open)}<br/>
              最高: ${formatNumber(high)}<br/>
              最低: ${formatNumber(low)}<br/>
              收盘: <span style="color:${color};font-weight:bold">${formatNumber(close)}</span><br/>
              涨跌: <span style="color:${color}">${up ? '+' : ''}${formatNumber(chg)} (${formatPct(chgPct)})</span><br/>
              成交量: ${formatVolume(vol)}
            </div>
          `
        },
      },
      grid: [
        { left: '10%', right: '8%', top: '18%', height: '52%' },
        { left: '10%', right: '8%', top: '75%', height: '15%' },
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          gridIndex: 0,
          axisLine: { lineStyle: { color: '#475569' } },
          axisTick: { show: false },
          axisLabel: { color: '#94A3B8', fontSize: 10 },
          splitLine: { show: false },
        },
        {
          type: 'category',
          data: dates,
          gridIndex: 1,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          type: 'value',
          gridIndex: 0,
          scale: true,
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94A3B8', fontSize: 10 },
        },
        {
          type: 'value',
          gridIndex: 1,
          scale: true,
          splitLine: { show: false },
          axisLabel: { color: '#94A3B8', fontSize: 9 },
        },
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: ohlcData,
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumeData,
        },
      ],
    }

    setOption(option)

    // ── Click handler ─────────────────────────────────────────────
    const chart = getChart()
    if (chart) {
      chart.off('click')
      chart.on('click', (params: any) => {
        if (params.seriesName === 'K线' && params.dataIndex != null) {
          const idx = params.dataIndex as number
          if (selectedIdxRef.current === idx) {
            updateStatsPanel(null)
          } else {
            updateStatsPanel(idx)
          }
        }
      })
    }

    // ── Screen-reader summary ─────────────────────────────────────
    const last = bars[bars.length - 1]
    setChartSummary(
      `${displaySymbol} ${displayName} 日线图，共 ${bars.length} 条数据，` +
        `最新收盘价 ${formatNumber(last.close)}，` +
        `最高 ${formatNumber(Math.max(...bars.map((b) => b.high)))}，` +
        `最低 ${formatNumber(Math.min(...bars.map((b) => b.low)))}`,
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bars, responseSymbol, stockName])

  // ── Scroll table row into view ──────────────────────────────────────
  useEffect(() => {
    if (selectedIdx !== null && tableBodyRef.current) {
      const row = tableBodyRef.current.querySelector(
        `tr[data-row-idx="${selectedIdx}"]`,
      )
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }, [selectedIdx])

  // ── Derived values ──────────────────────────────────────────────────
  const stats = computeStats(bars, selectedIdx)
  const hasData = bars.length > 0
  const displaySymbol = responseSymbol || symbol.toUpperCase()
  const displayName = stockName || displaySymbol

  const latestBar = bars.length > 0 ? bars[bars.length - 1] : null
  const prevBar = bars.length > 1 ? bars[bars.length - 2] : null
  const latestChange = latestBar && prevBar ? latestBar.close - prevBar.close : 0
  const latestChangePct = prevBar ? (latestChange / prevBar.close) * 100 : 0

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <div>
      <PageHero>
        <PageHeader
          title="K线数据"
          subtitle="查询 A 股日线 OHLCV 数据，可视化展示与交互分析"
        />
      </PageHero>

      {/* ── Form ──────────────────────────────────────────────────── */}
      <div className="card card-accent">
        <div className="card-header">
          <h2 className="card-title">查询参数</h2>
        </div>
        <div className="card-body">
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label" htmlFor="bars-symbol">
                  股票代码
                </label>
                <CreatableSelect
                  id="bars-symbol"
                  placeholder="输入代码或名称搜索股票…"
                  options={cachedStocks.map(s => ({
                    value: s.symbol,
                    label: `${s.symbol}${s.name ? ` - ${s.name}` : ''}`
                  }))}
                  value={symbol ? cachedStocks.find(s => s.symbol === symbol.toUpperCase())
                    ? { value: symbol.toUpperCase(), label: `${symbol.toUpperCase()}${cachedStocks.find(s => s.symbol === symbol.toUpperCase())?.name ? ` - ${cachedStocks.find(s => s.symbol === symbol.toUpperCase())!.name}` : ''}` }
                    : { value: symbol.toUpperCase(), label: symbol.toUpperCase() }
                    : null}
                  onChange={(o) => setSymbol(o?.value?.toUpperCase() || '')}
                  onCreateOption={(input) => setSymbol(input.toUpperCase())}
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
                  formatCreateLabel={(v) => `使用 "${v.toUpperCase()}"`}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="bars-period">
                  周期
                </label>
                <select
                  id="bars-period"
                  className="form-select"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  <option value="1y">近 1 年</option>
                  <option value="6m">近 6 个月</option>
                  <option value="3m">近 3 个月</option>
                  <option value="20d">近 20 个交易日</option>
                  <option value="60t">近 60 个交易日</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="bars-start">
                  开始日期
                </label>
                <input
                  id="bars-start"
                  className="form-input date-input"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="bars-end">
                  结束日期
                </label>
                <input
                  id="bars-end"
                  className="form-input date-input"
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>

            <div className="form-row" style={{ marginTop: 16 }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || !symbol.trim()}
              >
                {loading ? '查询中...' : '查询'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* ── Error ──────────────────────────────────────────────────── */}
      {error && (
        <div className="error-banner" style={{ marginTop: 16 }}>
          ⚠️ {error}
        </div>
      )}

      {/* ── Results ────────────────────────────────────────────────── */}
      {hasData && (
        <>
          {/* Info Bar */}
          <div className="card card-gradient" style={{ marginTop: 24 }}>
            <div className="card-body">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 12,
                }}
              >
                <div>
                  <h3 style={{ margin: 0, fontSize: 18, color: '#E2E8F0' }}>
                    {displayName}
                    <span
                      style={{
                        fontSize: 13,
                        color: '#94A3B8',
                        marginLeft: 8,
                      }}
                    >
                      {displaySymbol}
                    </span>
                  </h3>
                  {latestBar && (
                    <div style={{ marginTop: 4 }}>
                      <span
                        style={{
                          fontSize: 22,
                          fontWeight: 700,
                          color: '#F8FAFC',
                        }}
                      >
                        {formatNumber(latestBar.close)}
                      </span>
                      <span
                        style={{
                          marginLeft: 10,
                          fontSize: 15,
                          fontWeight: 600,
                          color: latestChange >= 0 ? '#EF4444' : '#22C55E',
                        }}
                      >
                        {latestChange >= 0 ? '▲' : '▼'}{' '}
                        {formatNumber(Math.abs(latestChange))} (
                        {formatPct(Math.abs(latestChangePct))})
                      </span>
                    </div>
                  )}
                </div>

                <div className="kpi-row">
                  <div className="kpi-item">
                    <span className="kpi-label">最新价</span>
                    <span className="kpi-value">
                      {latestBar ? formatNumber(latestBar.close) : '-'}
                    </span>
                  </div>
                  <div className="kpi-item">
                    <span className="kpi-label">涨跌</span>
                    <span
                      className="kpi-value"
                      style={{
                        color: latestChange >= 0 ? '#EF4444' : '#22C55E',
                      }}
                    >
                      {latestChange >= 0 ? '+' : ''}
                      {formatNumber(latestChange)}
                    </span>
                  </div>
                  <div className="kpi-item">
                    <span className="kpi-label">最高/最低</span>
                    <span className="kpi-value">
                      {latestBar
                        ? `${formatNumber(latestBar.high)} / ${formatNumber(latestBar.low)}`
                        : '-'}
                    </span>
                  </div>
                  <div className="kpi-item">
                    <span className="kpi-label">数据条数</span>
                    <span className="kpi-value">{bars.length}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Stats Grid */}
          {stats && (
            <div style={{ marginTop: 16 }}>
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label" id="bars-stat-label-0">
                    {stats.label0}
                  </div>
                  <div
                    className={`stat-value ${stats.className0}`}
                    id="bars-stat-val-0"
                  >
                    {stats.val0}
                  </div>
                  <div className="stat-sub" id="bars-stat-sub-0">
                    {stats.sub0}
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-label" id="bars-stat-label-1">
                    {stats.label1}
                  </div>
                  <div
                    className={`stat-value ${stats.className1}`}
                    id="bars-stat-val-1"
                  >
                    {stats.val1}
                  </div>
                  <div className="stat-sub" id="bars-stat-sub-1">
                    {stats.sub1}
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-label" id="bars-stat-label-2">
                    {stats.label2}
                  </div>
                  <div
                    className={`stat-value ${stats.className2}`}
                    id="bars-stat-val-2"
                  >
                    {stats.val2}
                  </div>
                  <div className="stat-sub" id="bars-stat-sub-2">
                    {stats.sub2}
                  </div>
                </div>

                <div className="stat-card">
                  <div className="stat-label" id="bars-stat-label-3">
                    {stats.label3}
                  </div>
                  <div
                    className={`stat-value ${stats.className3}`}
                    id="bars-stat-val-3"
                  >
                    {stats.val3}
                  </div>
                  <div className="stat-sub" id="bars-stat-sub-3">
                    {stats.sub3}
                  </div>
                </div>
              </div>

              {/* Selection hint / indicator */}
              <div
                style={{
                  marginTop: 8,
                  fontSize: 13,
                  color: '#94A3B8',
                  textAlign: 'center',
                }}
              >
                {selectedIdx !== null && stats.selectedDate ? (
                  <span>
                    📌 已选中{' '}
                    <strong style={{ color: '#C084FC' }}>
                      {stats.selectedDate}
                    </strong>{' '}
                    · 再次点击 K线取消选中 ·{' '}
                    <button
                      onClick={resetSelection}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: '#60A5FA',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        fontSize: 13,
                        padding: 0,
                      }}
                    >
                      返回最新
                    </button>
                  </span>
                ) : (
                  <span>💡 点击 K线柱可切换查看具体日期数据</span>
                )}
              </div>
            </div>
          )}

          {/* Chart */}
          <div className="chart-container large" style={{ marginTop: 20 }}>
            <div
              ref={chartContainerRef}
              style={{ width: '100%', height: 520 }}
            />
            <div className="sr-only" aria-live="polite">
              {chartSummary}
            </div>
          </div>

          {/* Data Table */}
          <div className="card" style={{ marginTop: 20 }}>
            <div className="card-header">
              <h3 className="card-title">数据明细</h3>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              <div
                className="table-container"
                style={{ maxHeight: 500, overflowY: 'auto' }}
              >
                <table
                  style={{ width: '100%', borderCollapse: 'collapse' }}
                >
                  <thead>
                    <tr
                      style={{
                        position: 'sticky',
                        top: 0,
                        background: '#1E293B',
                        zIndex: 1,
                      }}
                    >
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'left',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        日期
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        开盘
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        最高
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        最低
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        收盘
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        涨跌
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        成交量
                      </th>
                      <th
                        style={{
                          padding: '10px 12px',
                          textAlign: 'right',
                          color: '#94A3B8',
                          fontSize: 12,
                          borderBottom: '2px solid #334155',
                        }}
                      >
                        成交额
                      </th>
                    </tr>
                  </thead>
                  <tbody ref={tableBodyRef}>
                    {bars.map((bar, i) => {
                      const prev = i > 0 ? bars[i - 1] : null
                      const chg = prev ? bar.close - prev.close : 0
                      const isUp = bar.close >= bar.open
                      const isSelected = selectedIdx === i

                      return (
                        <tr
                          key={bar.date}
                          data-row-idx={i}
                          style={{
                            background: isSelected
                              ? 'rgba(168, 85, 247, 0.15)'
                              : i % 2 === 0
                                ? 'rgba(255,255,255,0.02)'
                                : 'transparent',
                            outline: isSelected
                              ? '2px solid #A855F7'
                              : 'none',
                            outlineOffset: -2,
                          }}
                        >
                          <td
                            style={{
                              padding: '8px 12px',
                              color: '#E2E8F0',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                            }}
                          >
                            {bar.date}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              color: '#F8FAFC',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            {formatNumber(bar.open)}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              color: '#F8FAFC',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            {formatNumber(bar.high)}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              color: '#F8FAFC',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            {formatNumber(bar.low)}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                              fontWeight: 600,
                            }}
                          >
                            <span
                              style={{
                                color: isUp ? '#EF4444' : '#22C55E',
                              }}
                            >
                              {isUp ? '▲' : '▼'}{' '}
                              {formatNumber(bar.close)}
                            </span>
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            <span
                              style={{
                                color: chg >= 0 ? '#EF4444' : '#22C55E',
                              }}
                            >
                              {chg >= 0 ? '+' : ''}
                              {formatNumber(chg)}
                            </span>
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              color: '#CBD5E1',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            {formatVolume(bar.volume)}
                          </td>
                          <td
                            style={{
                              padding: '8px 12px',
                              textAlign: 'right',
                              color: '#CBD5E1',
                              fontSize: 13,
                              borderBottom: '1px solid #1E293B',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
                            {formatAmount(bar.amount)}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── Empty state (initial) ──────────────────────────────────── */}
      {!hasData && !loading && !error && (
        <div style={{ marginTop: 24 }}>
          <EmptyState
            icon="📊"
            title="暂无数据"
            desc='请输入股票代码并点击"查询"获取 K 线数据'
          />
        </div>
      )}

      {/* ── Loading ────────────────────────────────────────────────── */}
      {loading && (
        <div
          style={{
            marginTop: 24,
            textAlign: 'center',
            color: '#94A3B8',
          }}
        >
          正在加载数据...
        </div>
      )}
    </div>
  )
}

export default Bars
