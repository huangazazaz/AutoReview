import type {
  AnalyzeResult,
  BacktestSummary,
  BarsResponse,
  StrategiesResponse,
  DatasourcesResponse,
  GroupsResponse,
  GroupInfo,
  CachedStocksResponse,
  HealthResponse,
  PortfolioBacktestResponse,
  AIStrategyGenerateResponse,
  SaveStrategyResponse,
  DeleteStrategyResponse,
  ChatRequest,
  ChatResponse,
  ChatHistoryResponse,
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  UserInfo,
} from '@/types'

const BASE = '/api'

function getToken(): string | null {
  return localStorage.getItem('auth_token')
}

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem('auth_token', token)
  } else {
    localStorage.removeItem('auth_token')
  }
}

// Called when a 401 is received — clears auth state and redirects to login
let onAuthExpired: (() => void) | null = null
export function setOnAuthExpired(fn: (() => void) | null) {
  onAuthExpired = fn
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  // Attach auth token if available
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const opts: RequestInit = {
    method,
    headers,
  }
  if (body !== undefined) {
    opts.body = JSON.stringify(body)
  }

  let res: Response
  try {
    res = await fetch(BASE + path, opts)
  } catch (err) {
    throw new Error(`网络错误：无法连接到服务器 (${(err as Error).message})`)
  }

  // Handle 401 — token expired or invalid
  if (res.status === 401) {
    setToken(null)
    if (onAuthExpired) onAuthExpired()
    throw new Error('登录已过期，请重新登录')
  }

  const data = await res.json()

  if (!res.ok) {
    if (res.status === 422 && data.detail) {
      const msgs = data.detail.map((d: { loc: string[]; msg: string }) => `${d.loc.join('.')}: ${d.msg}`).join('; ')
      throw new Error(`参数校验失败：${msgs}`)
    }
    throw new Error(data.error || data.detail || `请求失败 (HTTP ${res.status})`)
  }

  if (data.error) {
    throw new Error(data.error)
  }

  return data as T
}

function get<T>(path: string): Promise<T> { return request<T>('GET', path) }
function post<T>(path: string, body?: unknown): Promise<T> { return request<T>('POST', path, body) }
function put<T>(path: string, body?: unknown): Promise<T> { return request<T>('PUT', path, body) }
function del<T>(path: string): Promise<T> { return request<T>('DELETE', path) }

// ---- 公开 API ----

export const api = {
  health: () => get<HealthResponse>('/health'),

  analyze: (params: {
    symbol: string
    strategy?: string
    start?: string
    end?: string
    period?: string
    datasource?: string
    strategy_params?: Record<string, unknown>
  }) => post<AnalyzeResult>('/analyze', params),

  backtest: (params: {
    strategy?: string
    symbols?: string
    group?: string
    start?: string
    end?: string
    period?: string
    datasource?: string
    strategy_params?: Record<string, unknown>
  }) => post<BacktestSummary>('/backtest', params),

  getBars: (params: {
    symbol: string
    start?: string
    end?: string
    period?: string
  }) => post<BarsResponse>('/bars', params),

  getStrategies: () => get<StrategiesResponse>('/strategies'),

  getDatasources: () => get<DatasourcesResponse>('/datasources'),

  getGroups: () => get<GroupsResponse>('/groups'),

  getGroup: (id: string) => get<GroupInfo>('/groups/' + encodeURIComponent(id)),

  createGroup: (data: { id: string; name?: string; symbols: { code: string; name: string }[] }) =>
    post<GroupInfo>('/groups', data),

  updateGroup: (id: string, data: { name?: string; symbols?: { code: string; name: string }[] }) =>
    put<GroupInfo>('/groups/' + encodeURIComponent(id), data),

  deleteGroup: (id: string) =>
    del<{ ok: boolean; deleted: string }>('/groups/' + encodeURIComponent(id)),

  getCachedStocks: (params?: { page?: number; size?: number; keyword?: string; refresh?: boolean }) => {
    const qs = new URLSearchParams()
    if (params?.page) qs.set('page', String(params.page))
    if (params?.size) qs.set('size', String(params.size))
    if (params?.keyword) qs.set('keyword', params.keyword)
    if (params?.refresh) qs.set('refresh', 'true')
    const query = qs.toString()
    return get<CachedStocksResponse>('/cache/stocks' + (query ? '?' + query : ''))
  },

  portfolioBacktest: (params: {
    screener_name?: string
    strategy_name?: string
    strategy_params?: Record<string, unknown>
    strategy_buy_window?: number
    start?: string
    end?: string
    symbols?: string
    group?: string
    datasource?: string
  }) => post<PortfolioBacktestResponse>('/portfolio-backtest', params),

  generateStrategy: (params: {
    prompt: string
    symbol?: string
    start?: string
    end?: string
  }) => post<AIStrategyGenerateResponse>('/ai/generate-strategy', params),

  saveStrategy: (params: {
    name: string
    python_code: string
    yaml_code: string
  }) => post<SaveStrategyResponse>('/strategies/save', params),

  deleteStrategy: (name: string) => del<DeleteStrategyResponse>(`/strategies/${name}`),

  chat: (params: ChatRequest) => post<ChatResponse>('/ai/chat', params),

  getChatHistory: (sessionId: string) =>
    get<ChatHistoryResponse>('/ai/chat/' + encodeURIComponent(sessionId)),

  deleteChat: (sessionId: string) =>
    del<{ ok: boolean }>('/ai/chat/' + encodeURIComponent(sessionId)),

  // ---- 认证 ----
  login: (params: LoginRequest) => post<AuthResponse>('/auth/login', params),

  register: (params: RegisterRequest) => post<AuthResponse>('/auth/register', params),

  me: () => get<UserInfo>('/auth/me'),
}
