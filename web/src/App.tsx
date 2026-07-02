import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import ProtectedRoute from '@/components/ProtectedRoute'

// Lazy-loaded pages — each split into its own chunk
const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Login = lazy(() => import('@/pages/Login'))
const Register = lazy(() => import('@/pages/Register'))
const Analyze = lazy(() => import('@/pages/Analyze'))
const Backtest = lazy(() => import('@/pages/Backtest'))
const Portfolio = lazy(() => import('@/pages/Portfolio'))
const AIStrategy = lazy(() => import('@/pages/AIStrategy'))
const Bars = lazy(() => import('@/pages/Bars'))
const Groups = lazy(() => import('@/pages/Groups'))
const Screener = lazy(() => import('@/pages/Screener'))
const StrategyManage = lazy(() => import('@/pages/StrategyManage'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem 0' }}>
      <div className="spinner" />
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      {/* Auth pages — no sidebar */}
      <Route path="/login" element={<Suspense fallback={<PageLoader />}><Login /></Suspense>} />
      <Route path="/register" element={<Suspense fallback={<PageLoader />}><Register /></Suspense>} />

      {/* Protected routes — wrapped in Layout with sidebar */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>} />
          <Route path="/screener" element={<Suspense fallback={<PageLoader />}><Screener /></Suspense>} />
          <Route path="/analyze" element={<Suspense fallback={<PageLoader />}><Analyze /></Suspense>} />
          <Route path="/backtest" element={<Suspense fallback={<PageLoader />}><Backtest /></Suspense>} />
          <Route path="/portfolio" element={<Suspense fallback={<PageLoader />}><Portfolio /></Suspense>} />
          <Route path="/ai-strategy" element={<Suspense fallback={<PageLoader />}><AIStrategy /></Suspense>} />
          <Route path="/bars" element={<Suspense fallback={<PageLoader />}><Bars /></Suspense>} />
          <Route path="/groups" element={<Suspense fallback={<PageLoader />}><Groups /></Suspense>} />
          <Route path="/strategies" element={<Suspense fallback={<PageLoader />}><StrategyManage /></Suspense>} />
        </Route>
      </Route>
    </Routes>
  )
}
