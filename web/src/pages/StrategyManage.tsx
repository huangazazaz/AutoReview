import { useState, useEffect } from 'react'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHeader } from '@/components/UI'
import type { StrategyInfo } from '@/types'

export default function StrategyManage() {
  const { showToast, showLoading: showGlobalLoading, hideLoading } = useApp()

  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const loadStrategies = async () => {
    try {
      const data = await api.getStrategies()
      setStrategies(data.strategies)
    } catch (err) {
      showToast('加载策略列表失败', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadStrategies() }, [])

  const toggleExpand = (name: string) => {
    setExpanded(prev => ({ ...prev, [name]: !prev[name] }))
  }

  const handleDelete = async (name: string) => {
    showGlobalLoading(`正在删除策略 ${name}...`)
    try {
      const res = await api.deleteStrategy(name)
      if (res.error) {
        showToast(res.error, 'error')
      } else {
        showToast(`策略 ${name} 已删除`)
        setStrategies(prev => prev.filter(s => s.name !== name))
      }
    } catch (err) {
      showToast('删除失败: ' + (err as Error).message, 'error')
    } finally {
      hideLoading()
      setConfirmDelete(null)
    }
  }

  const builtins = strategies.filter(s => s.is_builtin)
  const customs = strategies.filter(s => !s.is_builtin)

  return (
    <>
      <PageHeader title="策略管理" subtitle="查看、管理交易策略及其参数配置" />

      {loading ? (
        <div className="card"><div className="card-body"><div className="empty-state"><p>加载中...</p></div></div></div>
      ) : (
        <>
          {/* 自定义策略 */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">✏️ 自定义策略</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>
                {customs.length} 个 — AI 生成或手动添加
              </span>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              {customs.length === 0 ? (
                <div className="empty-state" style={{ padding: 32 }}>
                  <p style={{ color: 'var(--text-muted)' }}>暂无自定义策略</p>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    前往 <a href="/ai-strategy" style={{ color: 'var(--accent)' }}>AI 策略</a> 页面生成新策略
                  </p>
                </div>
              ) : (
                <StrategyTable
                  strategies={customs}
                  expanded={expanded}
                  onToggle={toggleExpand}
                  confirmDelete={confirmDelete}
                  onConfirmDelete={setConfirmDelete}
                  onDelete={handleDelete}
                />
              )}
            </div>
          </div>

          {/* 内置策略 */}
          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header">
              <span className="card-title">🔒 内置策略</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>
                {builtins.length} 个 — 不可删除
              </span>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              <StrategyTable
                strategies={builtins}
                expanded={expanded}
                onToggle={toggleExpand}
                readonly
              />
            </div>
          </div>
        </>
      )}
    </>
  )
}

function StrategyTable({
  strategies,
  expanded,
  onToggle,
  readonly = false,
  confirmDelete,
  onConfirmDelete,
  onDelete,
}: {
  strategies: StrategyInfo[]
  expanded: Record<string, boolean>
  onToggle: (name: string) => void
  readonly?: boolean
  confirmDelete?: string | null
  onConfirmDelete?: (name: string | null) => void
  onDelete?: (name: string) => void
}) {
  if (strategies.length === 0) return null

  return (
    <div className="table-container" style={{ border: 'none' }}>
      <table>
        <thead>
          <tr>
            <th style={{ width: 180 }}>策略名</th>
            <th>参数</th>
            <th style={{ width: 80, textAlign: 'center' }}>详情</th>
            {!readonly && <th style={{ width: 80, textAlign: 'center' }}>操作</th>}
          </tr>
        </thead>
        <tbody>
          {strategies.map(s => {
            const isOpen = expanded[s.name] || false
            const schema = s.param_schema || {}
            const params = s.params || {}
            const paramCount = Object.keys(schema).length

            return (
              <>
                <tr key={s.name} style={{ cursor: 'pointer' }} onClick={() => onToggle(s.name)}>
                  <td>
                    <strong>{s.name}</strong>
                    {!readonly && <span className="tag" style={{ marginLeft: 6, fontSize: 10, background: 'var(--accent)', color: '#fff' }}>自定义</span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {Object.entries(schema).slice(0, 6).map(([k, v]) => {
                        const currentVal = params[k] !== undefined ? params[k] : v.default
                        return (
                          <code key={k} style={{
                            fontSize: 11, padding: '1px 6px',
                            background: 'var(--bg-card-hover)', borderRadius: 'var(--radius-sm)',
                            color: 'var(--text-secondary)',
                          }}>
                            {k}={JSON.stringify(currentVal)}
                          </code>
                        )
                      })}
                      {paramCount > 6 && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center' }}>
                          +{paramCount - 6} 更多
                        </span>
                      )}
                      {paramCount === 0 && <span className="text-muted" style={{ fontSize: 12 }}>无参数</span>}
                    </div>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                      {isOpen ? '▲ 收起' : '▼ 展开'}
                    </span>
                  </td>
                  {!readonly && (
                    <td style={{ textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                      {confirmDelete === s.name ? (
                        <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                          <button className="btn btn-sm" style={{ padding: '2px 8px', fontSize: 11, background: 'var(--error)', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)' }}
                            onClick={() => onDelete?.(s.name)}>确认</button>
                          <button className="btn btn-sm" style={{ padding: '2px 8px', fontSize: 11 }}
                            onClick={() => onConfirmDelete?.(null)}>取消</button>
                        </div>
                      ) : (
                        <button className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--error)', fontSize: 11, padding: '2px 6px' }}
                          onClick={() => onConfirmDelete?.(s.name)}>删除</button>
                      )}
                    </td>
                  )}
                </tr>
                {isOpen && (
                  <tr key={`${s.name}-detail`}>
                    <td colSpan={!readonly ? 4 : 3} style={{ padding: '12px 16px', background: 'var(--bg-card-hover)' }}>
                      <div className="param-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
                        {Object.entries(schema).map(([key, info]) => {
                          const currentVal = params[key] !== undefined ? params[key] : info.default
                          const typeLabel = info.type || '—'
                          return (
                            <div key={key} className="param-item">
                              <label className="param-label">
                                {key}
                                <span className="param-type-tag">{typeLabel}</span>
                              </label>
                              <div style={{ fontSize: 13, padding: '4px 8px', background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)' }}>
                                {JSON.stringify(currentVal)}
                              </div>
                            </div>
                          )
                        })}
                        {Object.keys(schema).length === 0 && (
                          <span className="text-muted" style={{ fontSize: 12 }}>此策略无配置参数</span>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
