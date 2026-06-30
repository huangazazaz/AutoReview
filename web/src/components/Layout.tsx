import { useState, useCallback } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Close mobile sidebar on route change
  const handleClose = useCallback(() => setMobileOpen(false), [])

  return (
    <>
      {/* 跳过导航 */}
      <a className="skip-link" href="#view-container">跳过导航，直达内容</a>

      {/* 侧边栏 */}
      <Sidebar mobileOpen={mobileOpen} onClose={handleClose} />

      {/* 移动端菜单按钮 */}
      <button
        className="menu-toggle"
        style={{ display: mobileOpen ? 'none' : undefined }}
        onClick={() => setMobileOpen(true)}
        aria-label="打开菜单"
        aria-expanded={mobileOpen}
        aria-controls="sidebar"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/>
        </svg>
      </button>

      {/* 主内容区 */}
      <main
        className="main-content"
        id="view-container"
        tabIndex={-1}
        onClick={mobileOpen ? handleClose : undefined}
      >
        <Outlet />
      </main>
    </>
  )
}
