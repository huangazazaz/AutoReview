import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHero, PageHeader, Skeleton, PulseDot } from '@/components/UI'
import type {
  HealthResponse,
  StrategiesResponse,
  DatasourcesResponse,
  GroupsResponse,
} from '@/types'

// ── Inline SVG icons ──────────────────────────────────────────────

const iconDashboard = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="9" rx="1" />
    <rect x="14" y="3" width="7" height="5" rx="1" />
    <rect x="14" y="12" width="7" height="9" rx="1" />
    <rect x="3" y="16" width="7" height="5" rx="1" />
  </svg>
)

const iconSearch = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
)

const iconChart = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" y1="20" x2="4" y2="12" />
    <line x1="9" y1="20" x2="9" y2="6" />
    <line x1="14" y1="20" x2="14" y2="14" />
    <line x1="19" y1="20" x2="19" y2="8" />
    <line x1="3" y1="20" x2="21" y2="20" />
  </svg>
)

const iconCandlestick = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="6" y1="4" x2="6" y2="20" />
    <line x1="10" y1="8" x2="10" y2="20" />
    <line x1="14" y1="3" x2="14" y2="20" />
    <line x1="18" y1="10" x2="18" y2="20" />
    <line x1="8" y1="16" x2="12" y2="16" />
    <line x1="12" y1="5" x2="16" y2="5" />
  </svg>
)

const iconFolder = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
  </svg>
)

const iconBrain = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 4a3 3 0 0 0-3 3c0 1.5.9 2.8 2.2 3.3A8 8 0 0 0 8 16v4h8v-4a8 8 0 0 0-3.2-5.7A3.5 3.5 0 0 0 15 7a3 3 0 0 0-3-3Z" />
  </svg>
)

const iconDatabase = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
)

// ── Component ─────────────────────────────────────────────────────

export default function Dashboard() {
  const { showToast } = useApp()

  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [strategies, setStrategies] = useState<StrategiesResponse | null>(null)
  const [datasources, setDatasources] = useState<DatasourcesResponse | null>(null)
  const [groups, setGroups] = useState<GroupsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      const results = await Promise.allSettled([
        api.health(),
        api.getStrategies(),
        api.getDatasources(),
        api.getGroups(),
      ])

      if (cancelled) return

      const [h, s, d, g] = results

      if (h.status === 'fulfilled') setHealth(h.value)
      else showToast('健康检查失败: ' + h.reason.message, 'error')

      if (s.status === 'fulfilled') setStrategies(s.value)
      else showToast('策略列表加载失败: ' + s.reason.message, 'error')

      if (d.status === 'fulfilled') setDatasources(d.value)
      else showToast('数据源列表加载失败: ' + d.reason.message, 'error')

      if (g.status === 'fulfilled') setGroups(g.value)
      else showToast('分组列表加载失败: ' + g.reason.message, 'error')

      setLoading(false)
    }

    load()

    return () => {
      cancelled = true
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const isOnline = health?.status === 'ok'
  const strategyCount = strategies?.strategies?.length ?? 0
  const datasourceCount = datasources?.datasources?.length ?? 0
  const groupCount = groups?.groups?.length ?? 0

  return (
    <div>
      {/* ── Hero ──────────────────────────────────────────────── */}
      <PageHero>
        <PageHeader
          title="仪表盘"
          subtitle="AutoTrade A股量化回测系统 · 实时状态概览"
        />
      </PageHero>

      {/* ── Stats Grid ────────────────────────────────────────── */}
      {loading ? (
        <Skeleton type="card" count={4} />
      ) : (
        <div className="stats-grid stagger">
          {/* API 状态 */}
          <div className="stat-card">
            <div className="stat-label">API 状态</div>
            <div className="row-stack" style={{ gap: 8, alignItems: 'center' }}>
              <PulseDot online={isOnline} />
              <span className={`stat-value ${isOnline ? 'stat-positive' : 'stat-negative'}`}>
                {isOnline ? '运行中' : '异常'}
              </span>
            </div>
          </div>

          {/* 可用策略 */}
          <div className="stat-card">
            <div className="stat-label">可用策略</div>
            <div className="stat-value stat-neutral">{strategyCount}</div>
            <div className="stat-sub">个策略</div>
          </div>

          {/* 数据源 */}
          <div className="stat-card">
            <div className="stat-label">数据源</div>
            <div className="stat-value stat-neutral">{datasourceCount}</div>
            <div className="stat-sub">个数据源</div>
          </div>

          {/* 分组 */}
          <div className="stat-card">
            <div className="stat-label">分组</div>
            <div className="stat-value stat-neutral">{groupCount}</div>
            <div className="stat-sub">个分组</div>
          </div>
        </div>
      )}

      {/* ── Quick Actions ──────────────────────────────────────── */}
      <h2 className="section-title animate-in">快捷操作</h2>
      <div className="quick-actions stagger">
        <Link to="/analyze" className="quick-action-card">
          <div className="qa-icon">{iconSearch}</div>
          <div className="qa-title">单股分析</div>
          <div className="qa-desc">对单只股票运行策略，查看信号与权益曲线</div>
        </Link>

        <Link to="/backtest" className="quick-action-card">
          <div className="qa-icon">{iconChart}</div>
          <div className="qa-title">批量回测</div>
          <div className="qa-desc">批量运行策略，汇总对比收益、夏普率等指标</div>
        </Link>

        <Link to="/bars" className="quick-action-card">
          <div className="qa-icon">{iconCandlestick}</div>
          <div className="qa-title">K线数据</div>
          <div className="qa-desc">查询任意股票的 OHLCV 历史 K 线数据</div>
        </Link>

        <Link to="/groups" className="quick-action-card">
          <div className="qa-icon">{iconFolder}</div>
          <div className="qa-title">分组管理</div>
          <div className="qa-desc">管理股票分组，便于批量回测和组合分析</div>
        </Link>
      </div>

      {/* ── System Resources ───────────────────────────────────── */}
      <h2 className="section-title animate-in" style={{ marginTop: 36 }}>系统资源</h2>

      <div className="row-stack grow" style={{ gap: 16 }}>
        {/* 可用策略列表 */}
        <div className="card card-accent" style={{ flex: 1 }}>
          <div className="card-header">
            <div className="row-stack" style={{ gap: 8, alignItems: 'center' }}>
              {iconBrain}
              <span className="card-title">可用策略</span>
            </div>
          </div>
          <div className="card-body">
            {loading ? (
              <Skeleton type="text" count={3} />
            ) : strategyCount === 0 ? (
              <p style={{ color: 'var(--text-secondary)' }}>暂无策略</p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {strategies!.strategies.map((s) => (
                  <span key={s.name} className="tag badge-outline">
                    {s.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 数据源列表 */}
        <div className="card card-accent" style={{ flex: 1 }}>
          <div className="card-header">
            <div className="row-stack" style={{ gap: 8, alignItems: 'center' }}>
              {iconDatabase}
              <span className="card-title">数据源</span>
            </div>
          </div>
          <div className="card-body">
            {loading ? (
              <Skeleton type="text" count={3} />
            ) : datasourceCount === 0 ? (
              <p style={{ color: 'var(--text-secondary)' }}>暂无数据源</p>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {datasources!.datasources.map((ds) => (
                  <span key={ds} className="tag badge-outline">
                    {ds}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
