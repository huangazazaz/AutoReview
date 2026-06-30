import type { StrategyResult, AIStrategyBacktest } from '@/types'
import { formatPct, formatNumber } from '@/utils/format'

interface StrategyCardProps {
  messageId: number
  strategy?: StrategyResult
  backtest?: AIStrategyBacktest
  codeExpanded: boolean
  onCodeExpand: (id: number) => void
  onSave?: (strategy: StrategyResult) => void
  onDelete?: (name: string) => void
  onCopy?: (code: string) => void
}

export default function StrategyCard({
  messageId,
  strategy,
  backtest,
  codeExpanded,
  onCodeExpand,
  onSave,
  onDelete,
  onCopy,
}: StrategyCardProps) {
  return (
    <div style={{ marginTop: 14 }}>
      {/* Backtest Metrics */}
      {backtest && (
        <div
          className="stats-grid"
          style={{
            marginTop: 8,
            marginBottom: 12,
            gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
          }}
        >
          <div
            className="stat-card"
            style={{
              borderTop: `2px solid ${backtest.return_pct >= 0 ? 'var(--buy)' : 'var(--sell)'}`,
              padding: '10px 14px',
            }}
          >
            <div className="stat-label">📈 收益率</div>
            <div
              className={
                'stat-value ' +
                (backtest.return_pct >= 0 ? 'stat-positive' : 'stat-negative')
              }
              style={{ fontSize: 16 }}
            >
              {formatPct(backtest.return_pct)}
            </div>
          </div>

          <div
            className="stat-card"
            style={{
              borderTop: '2px solid var(--accent)',
              padding: '10px 14px',
            }}
          >
            <div className="stat-label">🎯 胜率</div>
            <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>
              {formatPct(backtest.win_rate)}
            </div>
          </div>

          <div
            className="stat-card"
            style={{
              borderTop: '2px solid var(--info)',
              padding: '10px 14px',
            }}
          >
            <div className="stat-label">⚡ 夏普</div>
            <div className="stat-value stat-neutral" style={{ fontSize: 14 }}>
              {formatNumber(backtest.sharpe_ratio, 2)}
            </div>
          </div>

          <div
            className="stat-card"
            style={{
              borderTop: '2px solid var(--sell)',
              padding: '10px 14px',
            }}
          >
            <div className="stat-label">📉 最大回撤</div>
            <div className="stat-value stat-negative" style={{ fontSize: 14 }}>
              {formatPct(backtest.max_drawdown_pct)}
            </div>
          </div>
        </div>
      )}

      {/* Code Toggle & Block */}
      {strategy && (
        <div>
          <button
            className="params-toggle"
            onClick={() => onCodeExpand(messageId)}
          >
            <span className="toggle-icon">{codeExpanded ? '▼' : '▶'}</span>{' '}
            策略代码
          </button>
          {codeExpanded && (
            <div className="code-block" style={{ marginTop: 8 }}>
              <div className="code-header">
                <span className="code-lang">Python</span>
                <button
                  className="code-copy-btn"
                  onClick={() => {
                    if (onCopy) {
                      onCopy(strategy.python_code)
                    } else {
                      navigator.clipboard.writeText(strategy.python_code)
                    }
                  }}
                >
                  📋 复制
                </button>
              </div>
              <pre style={{ maxHeight: 300, overflow: 'auto' }}>
                <code>{strategy.python_code}</code>
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Action Buttons */}
      {strategy && (onSave || onDelete) && (
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          {onSave && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onSave(strategy)}
            >
              💾 保存策略
            </button>
          )}
          {onDelete && (
            <button
              className="btn btn-danger btn-sm"
              onClick={() => onDelete(strategy.name)}
            >
              🗑 删除
            </button>
          )}
        </div>
      )}
    </div>
  )
}
