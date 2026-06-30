import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import Dashboard from '@/pages/Dashboard'
import Analyze from '@/pages/Analyze'
import Backtest from '@/pages/Backtest'
import Portfolio from '@/pages/Portfolio'
import AIStrategy from '@/pages/AIStrategy'
import Bars from '@/pages/Bars'
import Groups from '@/pages/Groups'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/analyze" element={<Analyze />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/ai-strategy" element={<AIStrategy />} />
        <Route path="/bars" element={<Bars />} />
        <Route path="/groups" element={<Groups />} />
      </Route>
    </Routes>
  )
}
