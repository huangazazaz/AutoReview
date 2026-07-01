import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useApp } from '@/hooks/useApp'
import { useECharts } from '@/hooks/useECharts'
import { useCachedStocks } from '@/hooks/useCachedStocks'
import { useCachedStrategies } from '@/hooks/useCachedStrategies'
import { api } from '@/api/client'
import { PageHero, PageHeader, EmptyState, TrendIndicator } from '@/components/UI'
import StrategyParamsEditor from '@/components/StrategyParamsEditor'
import { formatNumber, formatPct, formatAmount, formatVolume, escapeHtml } from '@/utils/format'
import Select from 'react-select'
import CreatableSelect from 'react-select/creatable'
import type { AnalyzeResult, Bar, Trade } from '@/types'
import * as echarts from 'echarts'

/* ─────────────────────────────────────────────────────────────────────────────
   Constants
   ─────────────────────────────────────────────────────────────────────────── */

const PERIOD_OPTIONS = [
  { value: '1y', label: '1年' },
  { value: '6m', label: '6个月' },
  { value: '3m', label: '3个月' },
  { value: '20d', label: '20天' },
  { value: '60t', label: '60 ticks' },
]

const REASON_TAG_MAP: Record<string, string> = {
  '金叉': '🔺',
  '死叉': '🔻',
  '止盈': '✅',
  '止损': '⛔',
  '买入信号': '📈',
  '卖出信号': '📉',
  '突破': '🚀',
  '跌破': '💥',
  '超买': '🔴',
  '超卖': '🟢',
  '背离': '⚠️',
  '强制平仓': '💀',
}

/* ─────────────────────────────────────────────────────────────────────────────
   Helpers
   ─────────────────────────────────────────────────────────────────────────── */

function getPeriodDates(period: string): { start: string; end: string } {
  const now = new Date()
  const end = now.toISOString().slice(0, 10)
  if (period === '60t') return { start: '', end: '' }

  const d = new Date()
  switch (period) {
    case '1y':  d.setFullYear(d.getFullYear() - 1); break
    case '6m':  d.setMonth(d.getMonth() - 6);       break
    case '3m':  d.setMonth(d.getMonth() - 3);       break
    case '20d': d.setDate(d.getDate() - 20);        break
    default:    return { start: '', end }
  }
  return { start: d.toISOString().slice(0, 10), end }
}

function getReasonTag(reason: string): string {
  if (!reason) return '—'
  for (const [keyword, emoji] of Object.entries(REASON_TAG_MAP)) {
    if (reason.includes(keyword)) return `${emoji} ${escapeHtml(reason)}`
  }
  return escapeHtml(reason)
}

/** Build the full ECharts option for the equity-curve + K-line chart. */
function buildChartOption(
  result: AnalyzeResult,
  trades: Trade[],
  _bars: Bar[],
): echarts.EChartsOption {
  const curve = (result as any).equity_curve ?? []
  if (curve.length === 0) {
    return {
      backgroundColor: '#1E293B',
      title: { text: '权益曲线 + K线', left: 'center', textStyle: { color: '#E2E8F0', fontSize: 16 } },
      graphic: { type: 'text', left: 'center', top: 'center', style: { text: '暂无数据', fill: '#94A3B8', fontSize: 18 } },
    }
  }

  const dates = curve.map((d: any) => d.date ?? d.time ?? '')
  const equityData = curve.map((d: any) => d.equity ?? d.value ?? 0)
  const drawdownData = curve.map((d: any) => d.drawdown ?? 0)
  const closeData = curve.map((d: any) => (d.close != null ? d.close : null))

  const initialCapital = equityData.length > 0 ? equityData[0] : 100_000

  // Buy / Sell scatter points
  const buyData: [string, number][] = []
  const sellData: [string, number][] = []
  for (const trade of trades) {
    const idx = dates.indexOf(trade.date)
    if (idx < 0) continue
    const point: [string, number] = [trade.date, equityData[idx]]
    if (trade.action === 'BUY') { buyData.push(point) } else { sellData.push(point) }
  }

  // K-line data from bars: [open, close, low, high]
  const barMap = new Map<string, Bar>(_bars.map((b: Bar) => [b.date, b] as [string, Bar]))
  const klineData: number[][] = []
  const volumeData: { value: number; itemStyle: { color: string } }[] = []
  dates.forEach((d: string) => {
    const b = barMap.get(d)
    if (b) {
      klineData.push([b.open, b.close, b.low, b.high])
      const color = b.close >= b.open ? '#10B98133' : '#EF444433'
      volumeData.push({ value: b.volume, itemStyle: { color } })
    } else {
      klineData.push([0, 0, 0, 0])
      volumeData.push({ value: 0, itemStyle: { color: '#475569' } })
    }
  })

  // Gradients
  const purpleGradient = new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: 'rgba(168, 85, 247, 0.35)' },
    { offset: 1, color: 'rgba(168, 85, 247, 0.02)' },
  ])
  const greenGradient = new echarts.graphic.LinearGradient(0, 1, 0, 0, [
    { offset: 0, color: 'rgba(16, 185, 129, 0.30)' },
    { offset: 1, color: 'rgba(16, 185, 129, 0.02)' },
  ])

  // Grid layout: equity (top 32%), drawdown (middle 10%), K-line (bottom 58%)
  const datesX = dates.map((d: any) => String(d).length > 10 ? String(d).slice(5) : String(d))

  return {
    backgroundColor: '#1E293B',
    title: {
      text: '权益曲线 + K线',
      left: 'center',
      textStyle: { color: '#E2E8F0', fontSize: 16, fontWeight: 600 },
      top: 8,
    },
    legend: {
      bottom: 4,
      textStyle: { color: '#94A3B8', fontSize: 11 },
      itemWidth: 18,
      itemHeight: 10,
      data: ['权益', '收盘价', '回撤', '买入', '卖出'],
      selected: { '买入': true, '卖出': true, '收盘价': false },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderColor: '#475569',
      textStyle: { color: '#E2E8F0', fontSize: 12 },
      axisPointer: {
        type: 'cross',
        link: [{ xAxisIndex: 'all' }],
        label: { backgroundColor: '#334155' },
      },
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
    },
    grid: [
      { left: '8%', right: '10%', top: 48, height: '30%' },
      { left: '8%', right: '10%', top: '49%', height: '8%' },
      { left: '8%', right: '10%', top: '58%', height: '28%' },
      { left: '8%', right: '10%', top: '87%', height: '10%' },
    ],
    xAxis: [
      { type: 'category', data: datesX, gridIndex: 0, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8', fontSize: 10 }, axisTick: { show: false } },
      { type: 'category', data: datesX, gridIndex: 1, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { show: false }, axisTick: { show: false } },
      { type: 'category', data: datesX, gridIndex: 2, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { show: false }, axisTick: { show: false } },
      { type: 'category', data: datesX, gridIndex: 3, axisLine: { lineStyle: { color: '#334155' } }, axisLabel: { color: '#94A3B8', fontSize: 10 }, axisTick: { show: false } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, name: '权益', nameTextStyle: { color: '#94A3B8', fontSize: 11 }, axisLabel: { color: '#94A3B8', fontSize: 10, formatter: (v: number) => formatAmount(v) }, splitLine: { lineStyle: { color: '#1E293B' } } },
      { type: 'value', gridIndex: 0, name: '价格', nameTextStyle: { color: '#94A3B8', fontSize: 11 }, axisLabel: { color: '#94A3B8', fontSize: 10, formatter: (v: number) => formatNumber(v) }, splitLine: { show: false } },
      { type: 'value', gridIndex: 1, name: '回撤%', nameTextStyle: { color: '#94A3B8', fontSize: 10 }, axisLabel: { color: '#94A3B8', fontSize: 9, formatter: (v: number) => `${(v * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: '#1E293B' } } },
      { type: 'value', gridIndex: 2, name: '价格', nameTextStyle: { color: '#94A3B8', fontSize: 10 }, axisLabel: { color: '#94A3B8', fontSize: 10, formatter: (v: number) => formatNumber(v) }, splitLine: { lineStyle: { color: '#1E293B' } } },
      { type: 'value', gridIndex: 3, name: '量', nameTextStyle: { color: '#94A3B8', fontSize: 10 }, axisLabel: { color: '#94A3B8', fontSize: 9, formatter: (v: number) => formatVolume(v) }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2, 3], bottom: 28, height: 16, borderColor: '#334155', backgroundColor: '#0F172A', dataBackground: { lineStyle: { color: '#475569' }, areaStyle: { color: '#1E293B' } }, selectedDataBackground: { lineStyle: { color: '#A855F7' }, areaStyle: { color: 'rgba(168,85,247,0.15)' } }, textStyle: { color: '#94A3B8' } },
    ],
    series: [
      {
        name: '权益', type: 'line', data: equityData, smooth: true,
        lineStyle: { color: '#A855F7', width: 2 }, itemStyle: { color: '#A855F7' }, symbol: 'none',
        areaStyle: { color: purpleGradient }, z: 2,
        markPoint: { data: [{ type: 'max', name: '最高' }, { type: 'min', name: '最低' }], symbol: 'pin', symbolSize: 28, label: { color: '#E2E8F0', fontSize: 10 }, itemStyle: { color: '#A855F7' } },
      },
      {
        name: '收盘价', type: 'line', yAxisIndex: 1, data: closeData, smooth: true,
        lineStyle: { color: '#F59E0B', width: 1, type: 'dashed' }, itemStyle: { color: '#F59E0B' }, symbol: 'none', z: 1,
      },
      {
        name: '回撤', type: 'line', xAxisIndex: 1, yAxisIndex: 2, data: drawdownData,
        lineStyle: { color: '#10B981', width: 1.5 }, itemStyle: { color: '#10B981' },
        areaStyle: { color: greenGradient }, symbol: 'none', z: 1,
      },
      // K-line candlestick
      {
        name: 'K线', type: 'candlestick', xAxisIndex: 2, yAxisIndex: 3, data: klineData,
        itemStyle: { color: '#EF4444', color0: '#10B981', borderColor: '#EF4444', borderColor0: '#10B981' },
        z: 3,
      },
      // Volume
      {
        name: '成交量', type: 'bar', xAxisIndex: 3, yAxisIndex: 4, data: volumeData,
        z: 1,
      },
      ...(buyData.length > 0 ? [{
        name: '买入', type: 'scatter' as const, data: buyData.map(([d, v]) => [d, v]),
        symbol: 'triangle', symbolSize: 14, itemStyle: { color: '#FF4444' }, z: 10,
      }] : []),
      ...(sellData.length > 0 ? [{
        name: '卖出', type: 'scatter' as const, data: sellData.map(([d, v]) => [d, v]),
        symbol: 'triangle', symbolSize: 14, symbolRotate: 180, itemStyle: { color: '#22C55E' }, z: 10,
      }] : []),
    ],
  } as echarts.EChartsOption
}

/* ─────────────────────────────────────────────────────────────────────────────
   Component
   ─────────────────────────────────────────────────────────────────────────── */

export default function Analyze() {
  const app = useApp()
  const { initChart, setOption } = useECharts()

  /* ── Form state ────────────────────────────────────────────────────────── */
  const [symbol, setSymbol] = useState('')
  const [strategyName, setStrategyName] = useState('')
  const [period, setPeriod] = useState('1y')
  const [datasource, setDatasource] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [strategyParams, setStrategyParams] = useState<Record<string, string>>({})

  /* ── Reference / lookup data ───────────────────────────────────────────── */
  const { strategies } = useCachedStrategies()
  const [datasources, setDatasources] = useState<string[]>([])
  const { stocks: cachedStocks } = useCachedStocks()

  /* ── Results ───────────────────────────────────────────────────────────── */
  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [bars, setBars] = useState<Bar[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /* ── Refs ──────────────────────────────────────────────────────────────── */
  const chartContainerRef = useRef<HTMLDivElement | null>(null)
  const initialLoadDone = useRef(false)

  /* ── Derived ───────────────────────────────────────────────────────────── */
  const selectedStrategy = strategies.find((s) => s.name === strategyName) ?? undefined
  const stockName = cachedStocks.find((s) => s.symbol === symbol)?.name ?? ''

  const strategyOptions = useMemo(() => {
    const sys = strategies.filter(s => s.is_builtin)
    const usr = strategies.filter(s => !s.is_builtin)
    const groups: { label: string; options: { value: string; label: string }[] }[] = []
    if (sys.length) groups.push({ label: '系统策略', options: sys.map(s => ({ value: s.name, label: s.name })) })
    if (usr.length) groups.push({ label: '用户策略', options: usr.map(s => ({ value: s.name, label: s.name })) })
    return groups
  }, [strategies])

  /* ── Load lookups on mount ─────────────────────────────────────────────── */
  useEffect(() => {
    if (initialLoadDone.current) return
    initialLoadDone.current = true

    api.getDatasources()
      .then((r) => r.datasources)
      .catch(() => [] as string[])
      .then((dss) => setDatasources(dss))
  }, [])

  // Set default strategy when strategies first become available
  const defaultSet = useRef(false)
  useEffect(() => {
    if (defaultSet.current || strategies.length === 0) return
    // Only act when there's no valid strategy selected yet
    if (!strategyName || !strategies.find(s => s.name === strategyName)) {
      const def = strategies.find(s => s.name === 'ma_cross') ?? strategies[0]
      if (def) {
        setStrategyName(def.name)
        defaultSet.current = true
        // Populate params from YAML config values (same as handleStrategyChange)
        if (def.params) {
          const initial: Record<string, string> = {}
          for (const [key, val] of Object.entries(def.params)) {
            if (Array.isArray(val) || (typeof val === 'object' && val !== null)) {
              initial[key] = JSON.stringify(val)
            } else {
              initial[key] = String(val ?? '')
            }
          }
          setStrategyParams(initial)
        }
      }
    }
  }, [strategies, strategyName])

  /* ── Populate dates on period change ───────────────────────────────────── */
  const handlePeriodChange = useCallback((value: string) => {
    setPeriod(value)
    const { start, end } = getPeriodDates(value)
    setStartDate(start)
    setEndDate(end)
  }, [])

  // Set initial dates on first render
  useEffect(() => {
    const { start, end } = getPeriodDates('1y')
    setStartDate(start)
    setEndDate(end)
  }, [])

  /* ── Strategy change ───────────────────────────────────────────────────── */
  const handleStrategyChange = useCallback(
    (name: string) => {
      setStrategyName(name)
      const strat = strategies.find((s) => s.name === name)
      if (strat?.params) {
        // Reset overrides to strategy defaults
        const defaults: Record<string, string> = {}
        for (const [key, val] of Object.entries(strat.params)) {
          if (Array.isArray(val) || (typeof val === 'object' && val !== null)) {
            defaults[key] = JSON.stringify(val)
          } else {
            defaults[key] = String(val ?? '')
          }
        }
        setStrategyParams(defaults)
      } else {
        setStrategyParams({})
      }
    },
    [strategies],
  )

  /* ── Submit ────────────────────────────────────────────────────────────── */
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      setError(null)

      const trimmedSymbol = symbol.trim()
      if (!trimmedSymbol) {
        setError('请输入股票代码')
        return
      }

      setLoading(true)

      try {
        const analyzeParams = {
          symbol: trimmedSymbol,
          strategy: strategyName || undefined,
          period: period || undefined,
          datasource: datasource || '',
          start: startDate || undefined,
          end: endDate || undefined,
          strategy_params: Object.keys(strategyParams).length > 0 ? strategyParams : undefined,
        }

        const barsParams = {
          symbol: trimmedSymbol,
          period: period || undefined,
          start: startDate || undefined,
          end: endDate || undefined,
        }

        const [analyzeResult, barsResult] = await Promise.all([
          api.analyze(analyzeParams),
          api.getBars(barsParams).then((r) => r.bars).catch(() => [] as Bar[]),
        ])

        setResult(analyzeResult)
        setBars(barsResult)
      } catch (err: any) {
        setError(err?.message ?? '回测请求失败，请稍后重试')
        setResult(null)
        setBars([])
      } finally {
        setLoading(false)
      }
    },
    [symbol, strategyName, period, datasource, startDate, endDate, strategyParams],
  )

  /* ── Render chart when result changes ──────────────────────────────────── */
  useEffect(() => {
    if (!result || !chartContainerRef.current) return

    // Small delay so the DOM is laid out
    const timer = setTimeout(() => {
      if (chartContainerRef.current) {
        initChart(chartContainerRef.current)
        setOption(buildChartOption(result, result.trades ?? [], bars))
      }
    }, 100)

    return () => clearTimeout(timer)
  }, [result, bars, initChart, setOption])

  /* ── Derived stats from result ─────────────────────────────────────────── */
  const trades = result?.trades ?? []
  const metrics = result?.metrics

  const buyTrades = trades.filter((t) => t.action === 'BUY')
  const sellTrades = trades.filter((t) => t.action === 'SELL')

  const buyAmount = buyTrades.reduce((sum, t) => sum + t.price * t.quantity, 0)
  const sellAmount = sellTrades.reduce((sum, t) => sum + t.price * t.quantity, 0)
  const totalCommission = trades.reduce((sum, t) => sum + (t.commission ?? 0), 0)
  const totalStampDuty = trades.reduce((sum, t) => sum + (t.stamp_duty ?? 0), 0)
  const netProfit = metrics ? (metrics.final_equity ?? 0) - (metrics.initial_capital ?? 0) : 0

  /* ── Render ────────────────────────────────────────────────────────────── */
  return (
    <div className="analyze-page">
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <PageHero>
        <PageHeader
          title="单股分析"
          subtitle="对单只股票进行策略回测，查看权益曲线与交易明细"
        />
      </PageHero>

      {/* ── Form ────────────────────────────────────────────────────────── */}
      <form onSubmit={handleSubmit} className="card card-accent" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h2 className="card-title">回测参数</h2>
        </div>
        <div className="card-body">
          {/* Row 1: symbol + strategy + period */}
          <div className="form-row">
            <div className="form-group" style={{ flex: 2 }}>
              <label className="form-label" htmlFor="analyze-symbol">
                股票
              </label>
              <CreatableSelect
                id="analyze-symbol"
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

            <div className="form-group" style={{ flex: 2 }}>
              <label className="form-label" htmlFor="analyze-strategy">
                策略
              </label>
              <Select
                id="analyze-strategy"
                placeholder="请选择策略"
                options={strategyOptions}
                value={strategyName ? { value: strategyName, label: strategyName } : null}
                onChange={(o) => handleStrategyChange(o?.value || '')}
                isClearable
                isLoading={strategies.length === 0}
                loadingMessage={() => '正在加载策略…'}
                menuPortalTarget={document.body}
                className="react-select"
                classNamePrefix="rs"
              />
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label" htmlFor="analyze-period">
                周期
              </label>
              <Select
                id="analyze-period"
                options={PERIOD_OPTIONS}
                value={PERIOD_OPTIONS.find(p => p.value === period) || null}
                onChange={(o) => handlePeriodChange(o?.value || '1y')}
                menuPortalTarget={document.body}
                className="react-select"
                classNamePrefix="rs"
              />
            </div>
          </div>

          {/* Row 2: datasource + start + end */}
          <div className="form-row">
            <div className="form-group" style={{ flex: 2 }}>
              <label className="form-label" htmlFor="analyze-datasource">
                数据源
              </label>
              <Select
                id="analyze-datasource"
                placeholder="自动（主备降级）"
                options={[
                  { value: 'auto', label: '自动（主备降级）' },
                  ...datasources.filter(d => d !== 'auto').map(d => ({ value: d, label: d }))
                ]}
                value={datasource ? { value: datasource, label: datasource === 'auto' ? '自动（主备降级）' : datasource } : null}
                onChange={(o) => setDatasource(o?.value || '')}
                isClearable
                isLoading={datasources.length === 0}
                loadingMessage={() => '正在加载…'}
                menuPortalTarget={document.body}
                className="react-select"
                classNamePrefix="rs"
              />
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label" htmlFor="analyze-start">
                开始日期
              </label>
              <input
                id="analyze-start"
                className="form-input date-input"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>

            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label" htmlFor="analyze-end">
                结束日期
              </label>
              <input
                id="analyze-end"
                className="form-input date-input"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Strategy params editor */}
          {selectedStrategy && (
            <StrategyParamsEditor
              strategy={selectedStrategy}
              editParams={strategyParams}
              onChange={(key: string, value: string) =>
                setStrategyParams((prev) => ({ ...prev, [key]: value }))
              }
            />
          )}

          {/* Submit + error */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? '回测中...' : '开始回测'}
            </button>
            {error && (
              <span style={{ color: '#EF4444', fontSize: 13, fontWeight: 500 }}>{error}</span>
            )}
          </div>
        </div>
      </form>

      {/* ── Loading overlay ──────────────────────────────────────────────── */}
      {loading && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div style={{ textAlign: 'center', color: '#E2E8F0' }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>回测计算中...</div>
            <div style={{ fontSize: 13, color: '#94A3B8', marginTop: 4 }}>
              正在下载数据并执行策略
            </div>
          </div>
        </div>
      )}

      {/* ── Results ──────────────────────────────────────────────────────── */}
      {result && metrics && !loading && (
        <div className="analyze-results">
          {/* Stock title card */}
          <div
            className="card card-gradient"
            style={{
              background: 'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
              border: '1px solid #334155',
              marginBottom: 20,
            }}
          >
            <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#F1F5F9' }}>
                  {symbol}{' '}
                  <span style={{ fontWeight: 400, fontSize: 15, color: '#94A3B8' }}>
                    {stockName}
                  </span>
                </h2>
                <div style={{ marginTop: 4, fontSize: 13, color: '#94A3B8' }}>
                  策略：{selectedStrategy?.name ?? strategyName} &nbsp;|&nbsp; 周期：{period}
                </div>
              </div>
              <TrendIndicator up={(metrics.total_return_pct ?? 0) >= 0} />
            </div>
          </div>

          {/* Stats row 1: KPIs */}
          <div className="stats-grid" style={{ marginBottom: 16 }}>
            <div className="stat-card">
              <div className="stat-label">总收益率</div>
              <div className={`stat-value ${(metrics.total_return_pct ?? 0) >= 0 ? 'stat-positive' : 'stat-negative'}`}>
                {formatPct(metrics.total_return_pct ?? 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">胜率</div>
              <div className="stat-value stat-neutral">
                {formatPct(metrics.win_rate ?? 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">最大回撤</div>
              <div className="stat-value stat-negative">
                {formatPct(metrics.max_drawdown_pct ?? 0)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">夏普比率</div>
              <div className={`stat-value ${(metrics.sharpe_ratio ?? 0) >= 1 ? 'stat-positive' : 'stat-neutral'}`}>
                {formatNumber(metrics.sharpe_ratio ?? 0, 2)}
              </div>
            </div>
          </div>

          {/* Stats row 2: trade summary */}
          <div className="stats-grid" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="stat-label">总交易笔数</div>
              <div className="stat-value stat-neutral">{metrics.total_trades ?? 0}</div>
              <div className="stat-sub">
                买 {buyTrades.length} / 卖{' '}
                {sellTrades.length}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">买入总额</div>
              <div className="stat-value stat-neutral">{formatAmount(buyAmount)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">卖出总额</div>
              <div className="stat-value stat-neutral">{formatAmount(sellAmount)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">佣金 / 印花税</div>
              <div className="stat-value stat-neutral">
                {formatAmount(totalCommission)} / {formatAmount(totalStampDuty)}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">净收益</div>
              <div className={`stat-value ${netProfit >= 0 ? 'stat-positive' : 'stat-negative'}`}>
                {formatAmount(netProfit)}
              </div>
            </div>
          </div>

          {/* Equity curve chart */}
          <div className="chart-container kl-chart" style={{ marginBottom: 24 }}>
            <div
              ref={chartContainerRef}
              style={{ width: '100%', minHeight: 480 }}
            />
          </div>

          {/* Trade records table */}
          {trades.length > 0 ? (
            <div className="card" style={{ marginTop: 8 }}>
              <div className="card-header">
                <h3 className="card-title">交易记录</h3>
                <span style={{ fontSize: 13, color: '#94A3B8' }}>
                  共 {trades.length} 笔
                </span>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <div className="table-container">
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        <th>日期</th>
                        <th>操作</th>
                        <th>成交价</th>
                        <th>数量</th>
                        <th>成交金额</th>
                        <th>佣金</th>
                        <th>印花税</th>
                        <th>持仓</th>
                        <th>现金</th>
                        <th>总资产</th>
                        <th>触发原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((trade, i) => (
                        <tr
                          key={i}
                          style={{
                            backgroundColor:
                              trade.action === 'BUY'
                                ? 'rgba(239, 68, 68, 0.06)'
                                : 'rgba(34, 197, 94, 0.06)',
                          }}
                        >
                          <td>{trade.date}</td>
                          <td>
                            <span
                              className={`badge ${trade.action === 'BUY' ? 'badge-buy' : 'badge-sell'}`}
                            >
                              {trade.action === 'BUY' ? '买入' : '卖出'}
                            </span>
                          </td>
                          <td>{formatNumber(trade.price)}</td>
                          <td>{formatVolume(trade.quantity)}</td>
                          <td>{formatAmount(trade.price * trade.quantity)}</td>
                          <td>{formatAmount(trade.commission ?? 0)}</td>
                          <td>{formatAmount(trade.stamp_duty ?? 0)}</td>
                          <td>{formatNumber(trade.position)}</td>
                          <td>{formatAmount(trade.cash)}</td>
                          <td>{formatAmount(trade.total_equity)}</td>
                          <td>
                            <span
                              className="tag"
                              dangerouslySetInnerHTML={{
                                __html: getReasonTag(trade.reason ?? ''),
                              }}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            result && (
              <EmptyState
                icon="📭"
                title="暂无交易记录"
                desc="该策略在回测区间内未产生任何交易信号"
              />
            )
          )}
        </div>
      )}

      {/* ── Empty state: no results yet ──────────────────────────────────── */}
      {!result && !loading && (
        <EmptyState
          icon="📊"
          title="尚未分析"
          desc="请选择股票和策略参数，点击「开始回测」查看分析结果"
        />
      )}
    </div>
  )
}
