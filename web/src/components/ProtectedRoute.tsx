import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function ProtectedRoute() {
  const { isAuthenticated, isVerifying } = useAuth()

  if (isVerifying) {
    return (
      <div className="loading-overlay" style={{ display: 'flex' }}>
        <div className="spinner" />
        <p>验证登录状态...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
