import type { ReactNode } from 'react'

/** 页面标题 + 副标题 */
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="page-header" style={{ marginBottom: 0 }}>
      <h1 className="page-title">{title}</h1>
      {subtitle && <p className="page-subtitle" style={{ marginTop: 4 }}>{subtitle}</p>}
    </div>
  )
}

/** 英雄区渐变背景容器 */
export function PageHero({ children }: { children: ReactNode }) {
  return (
    <div className="page-hero">{children}</div>
  )
}

/** 骨架屏 */
export function Skeleton({ type = 'text', count = 3 }: { type?: 'card' | 'table' | 'text'; count?: number }) {
  if (type === 'card') {
    return (
      <div className="stats-grid">
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="stat-card">
            <div className="skeleton skeleton-title" />
            <div className="skeleton skeleton-text" />
            <div className="skeleton skeleton-text" />
          </div>
        ))}
      </div>
    )
  }
  if (type === 'table') {
    return (
      <>
        {Array.from({ length: count }, (_, i) => (
          <div key={i} className="skeleton skeleton-row" style={{ marginBottom: 8 }} />
        ))}
      </>
    )
  }
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton skeleton-text" />
      ))}
    </>
  )
}

/** 空状态 */
export function EmptyState({ icon, title, desc }: { icon?: ReactNode; title?: string; desc?: string }) {
  return (
    <div className="empty-state-enhanced">
      {icon && <div className="empty-icon-bg">{icon}</div>}
      {title && <div className="empty-title">{title}</div>}
      {desc && <div className="empty-desc">{desc}</div>}
    </div>
  )
}

/** 脉冲指示点 */
export function PulseDot({ online }: { online: boolean }) {
  return <span className={`pulse-dot ${online ? 'online' : 'offline'}`} />
}

/** 趋势指示器 */
export function TrendIndicator({ up }: { up: boolean }) {
  return (
    <span className={`trend-indicator ${up ? 'trend-up' : 'trend-down'}`}>
      <span className="trend-arrow">{up ? '▲' : '▼'}</span>
    </span>
  )
}

/** 分割线 */
export function Divider({ soft = false }: { soft?: boolean }) {
  return <hr className={soft ? 'divider-soft' : 'divider'} />
}
