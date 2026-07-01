import { Link } from 'react-router-dom'

const features = [
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      </svg>
    ),
    title: '单股分析',
    desc: '对单只股票运行策略回测，查看买卖信号、权益曲线和详细交易记录。',
    to: '/analyze',
    color: '#3B82F6',
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="4" y1="20" x2="4" y2="12" /><line x1="9" y1="20" x2="9" y2="6" />
        <line x1="14" y1="20" x2="14" y2="14" /><line x1="19" y1="20" x2="19" y2="8" />
        <line x1="3" y1="20" x2="21" y2="20" />
      </svg>
    ),
    title: '批量回测',
    desc: '批量运行策略，汇总对比收益率、夏普比率、最大回撤等核心指标。',
    to: '/backtest',
    color: '#22C55E',
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" /><path d="M7 16l4-6 4 3 3-5" />
        <circle cx="7" cy="16" r="1.5" fill="currentColor" fillOpacity="0.3" />
        <circle cx="17" cy="8" r="1.5" fill="currentColor" fillOpacity="0.3" />
      </svg>
    ),
    title: '组合回测',
    desc: 'Screener 选股 + 策略择时的多持仓组合回测，含完整交易记录与权益曲线。',
    to: '/portfolio',
    color: '#F59E0B',
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a4 4 0 0 1 4 4v1h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2V6a4 4 0 0 1 4-4Z" />
        <circle cx="12" cy="14" r="2" fill="currentColor" fillOpacity="0.3" />
      </svg>
    ),
    title: 'AI 策略',
    desc: '用自然语言描述交易想法，AI 自动生成策略代码并立即回测验证效果。',
    to: '/ai-strategy',
    color: '#8B5CF6',
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="6" y="4" width="4" height="7" rx="1" /><line x1="8" y1="3" x2="8" y2="4" /><line x1="8" y1="11" x2="8" y2="13" />
        <rect x="14" y="9" width="4" height="6" rx="1" /><line x1="16" y1="7" x2="16" y2="9" /><line x1="16" y1="15" x2="16" y2="18" />
      </svg>
    ),
    title: 'K线数据',
    desc: '查询任意 A 股的 OHLCV 历史日线数据，支持交互式 K 线图表展示。',
    to: '/bars',
    color: '#EF4444',
  },
  {
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.89l-.82-1.22A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z" />
      </svg>
    ),
    title: '分组管理',
    desc: '创建和管理股票分组，内置银行、科技等行业分组，支持自定义。',
    to: '/groups',
    color: '#06B6D4',
  },
]

export default function Dashboard() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Hero */}
      <div style={{ textAlign: 'center', padding: '48px 0 40px' }}>
        <h1 style={{
          fontSize: 36, fontWeight: 800, margin: '0 0 12px',
          background: 'linear-gradient(135deg, #F59E0B 0%, #8B5CF6 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          letterSpacing: '-0.02em',
        }}>
          BacktestLab
        </h1>
        <p style={{
          fontSize: 17, color: 'var(--text-secondary)', margin: '0 0 8px',
          maxWidth: 520, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.7,
        }}>
          A 股量化回测系统 —— 策略回测、AI 生成、组合分析，一站式量化研究工具
        </p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 24 }}>
          <Link to="/analyze" className="btn btn-primary" style={{ padding: '10px 28px', fontSize: 15, fontWeight: 600 }}>
            开始回测
          </Link>
          <Link to="/ai-strategy" className="btn btn-secondary" style={{ padding: '10px 28px', fontSize: 15 }}>
            AI 生成策略
          </Link>
        </div>
      </div>

      {/* Feature Cards */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 16, marginTop: 8,
      }}>
        {features.map((f) => (
          <Link
            key={f.to}
            to={f.to}
            style={{
              display: 'block', padding: '24px 20px', borderRadius: 'var(--radius-lg)',
              background: 'var(--surface)', border: '1px solid var(--border)',
              textDecoration: 'none', color: 'inherit',
              transition: 'border-color 0.2s, transform 0.15s, box-shadow 0.15s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = f.color
              e.currentTarget.style.boxShadow = `0 4px 24px ${f.color}15`
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = ''
              e.currentTarget.style.boxShadow = ''
            }}
          >
            <div style={{
              width: 48, height: 48, borderRadius: 12, display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              background: `${f.color}15`, color: f.color, marginBottom: 16,
            }}>
              {f.icon}
            </div>
            <h3 style={{ margin: '0 0 6px', fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>
              {f.title}
            </h3>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              {f.desc}
            </p>
          </Link>
        ))}
      </div>

      {/* Footer */}
      <div style={{
        textAlign: 'center', padding: '48px 0 24px',
        color: 'var(--text-muted)', fontSize: 13,
      }}>
        <p style={{ margin: '0 0 4px' }}>
          数据来源: AKShare · 支持 A 股全市场日线数据
        </p>
        <p style={{ margin: 0 }}>
          BacktestLab v0.1.0 · dev/autotrade-mvp
        </p>
      </div>
    </div>
  )
}
