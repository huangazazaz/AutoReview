import { NavLink } from 'react-router-dom'

interface SidebarProps {
  mobileOpen?: boolean
  onClose?: () => void
}

const navItems = [
  { path: '/', label: '仪表盘', icon: 'dashboard' },
  { path: '/analyze', label: '单股分析', icon: 'search' },
  { path: '/backtest', label: '批量回测', icon: 'chart' },
  { path: '/portfolio', label: '组合回测', icon: 'portfolio' },
  { path: '/bars', label: 'K线数据', icon: 'candlestick' },
  { path: '/groups', label: '分组管理', icon: 'folder' },
]

const svgIcons: Record<string, JSX.Element> = {
  dashboard: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/>
      <rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>
    </svg>
  ),
  search: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
  ),
  chart: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  candlestick: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="6" y="4" width="4" height="7" rx="0.5"/><line x1="8" y1="3" x2="8" y2="4"/>
      <line x1="8" y1="11" x2="8" y2="13"/><rect x="14" y="9" width="4" height="6" rx="0.5"/>
      <line x1="16" y1="7" x2="16" y2="9"/><line x1="16" y1="15" x2="16" y2="18"/>
    </svg>
  ),
  folder: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.89l-.82-1.22A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>
    </svg>
  ),
  portfolio: (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18"/>
      <path d="M7 16l4-6 4 3 3-5"/>
      <circle cx="7" cy="16" r="1" fill="currentColor" fillOpacity="0.5"/>
      <circle cx="17" cy="8" r="1" fill="currentColor" fillOpacity="0.5"/>
    </svg>
  ),
}

export default function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const className = 'sidebar' + (mobileOpen ? ' open' : '')

  return (
    <aside className={className} id="sidebar">
      <div className="sidebar-brand">
        <span className="brand-icon">
          <svg className="icon brand-logo" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="2" y="4" width="20" height="16" rx="3" fill="currentColor" fillOpacity="0.12"/>
            <polyline points="7 17 10 10 13 14 16 7 18 11"/>
            <circle cx="7" cy="17" r="1" fill="currentColor" fillOpacity="0.5"/>
            <circle cx="18" cy="11" r="1" fill="currentColor" fillOpacity="0.5"/>
          </svg>
        </span>
        <span className="brand-text">AutoTrade</span>
      </div>
      <nav className="sidebar-nav">
        {navItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
            onClick={onClose}
          >
            <span className="nav-icon">{svgIcons[item.icon]}</span>
            <span className="nav-label">{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-footer">
        <span className="version"><span className="version-text">v0.1.0</span></span>
      </div>
    </aside>
  )
}
