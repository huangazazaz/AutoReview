/** 后端 API 响应类型 */

// ---- K线 ----
export interface Bar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

export interface BarsResponse {
  symbol: string
  stock_name: string
  count: number
  start: string
  end: string
  bars: Bar[]
  error?: string
}

// ---- 交易 / 回测 ----
export interface Trade {
  date: string
  action: 'BUY' | 'SELL'
  price: number
  quantity: number
  commission: number
  stamp_duty: number
  position: number
  cash: number
  total_equity: number
  reason: string
}

export interface EquityPoint {
  date: string
  equity: number
}

export interface AnalyzeResult {
  symbol: string
  stock_name: string
  metrics: Record<string, number>
  trades: Trade[]
  signal_count: number
  equity_curve: EquityPoint[] | null
}

export interface BacktestResultItem {
  symbol: string
  stock_name: string
  trades: number
  return_pct: number
  sharpe: number
  max_drawdown_pct: number
  win_rate: number
}

export interface BacktestSummary {
  total: number
  success: number
  failed: number
  avg_return_pct?: number
  positive_count?: number
  negative_count?: number
  best_symbol?: string
  best_return?: number
  worst_symbol?: string
  worst_return?: number
  results: BacktestResultItem[]
  error?: string
}

// ---- 策略 ----
export interface ParamSchemaEntry {
  default?: unknown
  type?: string
}

export interface StrategyInfo {
  name: string
  params: Record<string, unknown>
  param_schema?: Record<string, ParamSchemaEntry>
}

export interface StrategiesResponse {
  strategies: StrategyInfo[]
}

// ---- 数据源 ----
export interface DatasourcesResponse {
  datasources: string[]
}

// ---- 分组 ----
export interface GroupSymbol {
  code: string
  name: string
}

export interface GroupInfo {
  id: string
  name: string
  symbols: GroupSymbol[]
}

export interface GroupsResponse {
  groups: GroupInfo[]
}

// ---- 缓存股票 ----
export interface CachedStock {
  symbol: string
  name: string
  bars: number
  start: string | null
  end: string | null
  last_close: number | null
}

export interface CachedStocksResponse {
  symbols: CachedStock[]
  total?: number
  page?: number
  size?: number
  pages?: number
}

// ---- 健康检查 ----
export interface HealthResponse {
  status: string
}

// ---- 通用 ----
export interface ErrorResponse {
  error: string
}

// ---- 组合/账户回测 ----
export interface PortfolioBacktestMetrics {
  initial_capital: number
  final_equity: number
  total_trades: number
  total_return_pct: number
  win_rate: number
  max_drawdown_pct: number
  sharpe_ratio: number
}

export interface PortfolioBacktestResponse {
  metrics?: PortfolioBacktestMetrics
  trade_count: number
  output_dir: string
  error?: string
}

// ---- AI 策略生成 ----
export interface AIStrategyBacktest {
  symbol: string
  return_pct: number
  win_rate: number
  sharpe_ratio: number
  max_drawdown_pct: number
  total_trades: number
}

export interface AIStrategyGenerateResponse {
  name: string
  display_name: string
  description: string
  python_code: string
  yaml_code: string
  reasoning: string
  backtest: AIStrategyBacktest | null
  error?: string
  raw?: string
}

export interface SaveStrategyResponse {
  success?: boolean
  name: string
  python_path?: string
  yaml_path?: string
  error?: string
}

export interface DeleteStrategyResponse {
  success?: boolean
  name: string
  deleted?: string[]
  error?: string
}
