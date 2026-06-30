import { useState, useEffect, useCallback } from 'react'
import { useApp } from '@/hooks/useApp'
import { api } from '@/api/client'
import { PageHero, PageHeader, EmptyState } from '@/components/UI'
import { escapeHtml } from '@/utils/format'
import type { GroupInfo, GroupSymbol } from '@/types'

// ── Helpers ──────────────────────────────────────────────────────────────────

function stockCount(g: GroupInfo): number {
  if (g.symbols) return g.symbols.length
  if (typeof (g as any).count === 'number') return (g as any).count
  return 0
}

// ── Component ────────────────────────────────────────────────────────────────

function Groups() {
  const { showConfirm, showToast } = useApp()

  // ── Page state ───────────────────────────────────────────────────────────

  const [groups, setGroups] = useState<GroupInfo[]>([])
  const [currentGroupId, setCurrentGroupId] = useState<string | null>(null)
  const [groupDetail, setGroupDetail] = useState<GroupInfo | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // ── Modal state ──────────────────────────────────────────────────────────

  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create')
  const [modalGroupId, setModalGroupId] = useState('')
  const [modalGroupName, setModalGroupName] = useState('')
  const [modalSymbols, setModalSymbols] = useState<{ code: string; name: string }[]>([
    { code: '', name: '' },
  ])
  const [modalError, setModalError] = useState('')
  const [modalSaving, setModalSaving] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)

  // ── Load group list ──────────────────────────────────────────────────────

  const loadGroups = useCallback(async () => {
    try {
      const data = await api.getGroups()
      setGroups(data.groups)
    } catch (err: any) {
      showToast(err?.message || '加载分组列表失败', 'error')
    }
  }, [showToast])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  // ── Load group detail ────────────────────────────────────────────────────

  const loadGroupDetail = useCallback(
    async (id: string) => {
      setDetailLoading(true)
      try {
        const data = await api.getGroup(id)
        setGroupDetail(data)
      } catch (err: any) {
        showToast(err?.message || '加载分组详情失败', 'error')
        setGroupDetail(null)
      } finally {
        setDetailLoading(false)
      }
    },
    [showToast],
  )

  // ── Group list interaction ───────────────────────────────────────────────

  const handleGroupClick = useCallback(
    (groupId: string) => {
      setCurrentGroupId(groupId)
      loadGroupDetail(groupId)
    },
    [loadGroupDetail],
  )

  const handleGroupKeyDown = useCallback(
    (e: React.KeyboardEvent, groupId: string) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        handleGroupClick(groupId)
      }
    },
    [handleGroupClick],
  )

  // ── Delete ───────────────────────────────────────────────────────────────

  const handleDelete = useCallback(async () => {
    if (!currentGroupId) return

    const confirmed = await showConfirm('确认删除该分组？此操作不可撤销。')
    if (!confirmed) return

    try {
      await api.deleteGroup(currentGroupId)
      showToast('分组已删除', 'success')
      setCurrentGroupId(null)
      setGroupDetail(null)
      await loadGroups()
    } catch (err: any) {
      showToast(err?.message || '删除分组失败', 'error')
    }
  }, [currentGroupId, showConfirm, showToast, loadGroups])

  // ── Modal save handler ───────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    // Validate
    if (!modalGroupId.trim()) {
      setModalError('分组ID不能为空')
      return
    }
    if (!modalGroupName.trim()) {
      setModalError('分组名称不能为空')
      return
    }

    // Collect non-empty symbol rows
    const symbols: GroupSymbol[] = modalSymbols
      .filter((s) => s.code.trim() !== '')
      .map((s) => ({ code: s.code.trim(), name: s.name.trim() }))

    setModalSaving(true)
    setModalError('')

    try {
      if (modalMode === 'create') {
        const result = await api.createGroup({
          id: modalGroupId.trim(),
          name: modalGroupName.trim(),
          symbols,
        })
        showToast('分组创建成功', 'success')
        setModalVisible(false)
        await loadGroups()
        const newId = result?.id ?? modalGroupId.trim()
        setCurrentGroupId(newId)
        await loadGroupDetail(newId)
      } else {
        await api.updateGroup(modalGroupId.trim(), {
          name: modalGroupName.trim(),
          symbols,
        })
        showToast('分组更新成功', 'success')
        setModalVisible(false)
        await loadGroups()
        setCurrentGroupId(modalGroupId.trim())
        await loadGroupDetail(modalGroupId.trim())
      }
    } catch (err: any) {
      setModalError(err?.message || (modalMode === 'create' ? '创建分组失败' : '更新分组失败'))
    } finally {
      setModalSaving(false)
    }
  }, [modalMode, modalGroupId, modalGroupName, modalSymbols, showToast, loadGroups, loadGroupDetail])

  // ── Open modal ───────────────────────────────────────────────────────────

  const openCreateModal = useCallback(() => {
    setModalMode('create')
    setModalGroupId('')
    setModalGroupName('')
    setModalSymbols([{ code: '', name: '' }])
    setModalError('')
    setModalSaving(false)
    setModalVisible(true)
  }, [])

  const openEditModal = useCallback(() => {
    if (!groupDetail) return
    setModalMode('edit')
    setModalGroupId(groupDetail.id)
    setModalGroupName(groupDetail.name)
    setModalSymbols(
      groupDetail.symbols && groupDetail.symbols.length > 0
        ? groupDetail.symbols.map((s) => ({ code: s.code, name: s.name }))
        : [{ code: '', name: '' }],
    )
    setModalError('')
    setModalSaving(false)
    setModalVisible(true)
  }, [groupDetail])

  // ── Close modal ──────────────────────────────────────────────────────────

  const closeModal = useCallback(() => {
    setModalVisible(false)
  }, [])

  // ── JSX ──────────────────────────────────────────────────────────────────

  return (
    <div>
      <PageHero>
        <PageHeader title="分组管理" subtitle="创建和管理股票分组，便于批量查看和分析" />
      </PageHero>

      <div className="split-layout">
        {/* ── Left panel: group list ─────────────────────────────────── */}
        <div className="split-left card card-accent">
          <div className="card-header">
            <h2 className="card-title">分组列表</h2>
            <button
              className="btn btn-primary btn-sm"
              type="button"
              onClick={openCreateModal}
            >
              新建分组
            </button>
          </div>
          <div className="card-body">
            {groups.length === 0 ? (
              <div className="empty-state-enhanced">
                <div className="empty-icon-bg">
                  <span className="empty-icon" aria-hidden="true">
                    📁
                  </span>
                </div>
                <p className="empty-title">暂无分组</p>
                <p className="empty-desc">
                  点击&ldquo;新建分组&rdquo;创建您的第一个股票分组
                </p>
              </div>
            ) : (
              <ul
                style={{ listStyle: 'none', padding: 0, margin: 0 }}
                role="listbox"
                aria-label="分组列表"
              >
                {groups.map((g) => (
                  <li
                    key={g.id}
                    className={`group-list-item${currentGroupId === g.id ? ' active' : ''}`}
                    role="option"
                    aria-selected={currentGroupId === g.id}
                    tabIndex={0}
                    onClick={() => handleGroupClick(g.id)}
                    onKeyDown={(e) => handleGroupKeyDown(e, g.id)}
                  >
                    <span
                      className="group-name"
                      dangerouslySetInnerHTML={{ __html: escapeHtml(g.name) }}
                    />
                    <span className="group-count">{stockCount(g)} 只股票</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* ── Right panel: detail / empty ────────────────────────────── */}
        <div className="split-right card card-accent">
          {!currentGroupId || !groupDetail ? (
            <EmptyState
              icon={<span>📋</span>}
              title="选择一个分组"
              desc="请从左侧列表选择一个分组查看或编辑"
            />
          ) : detailLoading ? (
            <div
              className="card-body"
              style={{ textAlign: 'center', padding: '2rem' }}
            >
              <p>加载中...</p>
            </div>
          ) : (
            <>
              <div className="card-header">
                <h2
                  className="card-title"
                  dangerouslySetInnerHTML={{ __html: escapeHtml(groupDetail.name) }}
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    type="button"
                    onClick={openEditModal}
                  >
                    编辑
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    type="button"
                    onClick={handleDelete}
                  >
                    删除
                  </button>
                </div>
              </div>
              <div className="card-body">
                <p
                  style={{
                    margin: 0,
                    color: 'var(--color-text-secondary, #666)',
                    fontSize: '0.875rem',
                  }}
                >
                  分组ID：{escapeHtml(groupDetail.id)}
                </p>
                <p
                  style={{
                    margin: '4px 0 16px',
                    color: 'var(--color-text-secondary, #666)',
                    fontSize: '0.875rem',
                  }}
                >
                  包含 <strong>{stockCount(groupDetail)}</strong> 只股票
                </p>

                {groupDetail.symbols && groupDetail.symbols.length > 0 ? (
                  <div className="table-container">
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr>
                          <th
                            style={{
                              textAlign: 'left',
                              padding: '8px 12px',
                              borderBottom:
                                '2px solid var(--color-border, #e0e0e0)',
                            }}
                          >
                            代码
                          </th>
                          <th
                            style={{
                              textAlign: 'left',
                              padding: '8px 12px',
                              borderBottom:
                                '2px solid var(--color-border, #e0e0e0)',
                            }}
                          >
                            名称
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {groupDetail.symbols.map((sym, i) => (
                          <tr key={i}>
                            <td
                              style={{
                                padding: '6px 12px',
                                borderBottom:
                                  '1px solid var(--color-border-light, #f0f0f0)',
                              }}
                              dangerouslySetInnerHTML={{
                                __html: escapeHtml(sym.code),
                              }}
                            />
                            <td
                              style={{
                                padding: '6px 12px',
                                borderBottom:
                                  '1px solid var(--color-border-light, #f0f0f0)',
                              }}
                              dangerouslySetInnerHTML={{
                                __html: escapeHtml(sym.name),
                              }}
                            />
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state-enhanced">
                    <p className="empty-desc">
                      该分组暂无股票，点击&ldquo;编辑&rdquo;添加
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Modal: create / edit group ─────────────────────────────────── */}
      {modalVisible && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">
                {modalMode === 'create' ? '新建分组' : '编辑分组'}
              </span>
              <button className="modal-close" onClick={closeModal}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              {modalError && (
                <div
                  className="error-banner"
                  role="alert"
                  dangerouslySetInnerHTML={{ __html: escapeHtml(modalError) }}
                />
              )}

              {modalMode === 'edit' && (
                <div className="form-group">
                  <label className="form-label">分组ID</label>
                  <input
                    className="form-input"
                    type="text"
                    value={modalGroupId}
                    disabled
                  />
                  <span className="form-hint">分组ID不可修改</span>
                </div>
              )}

              {modalMode === 'create' && (
                <div className="form-group">
                  <label className="form-label required">分组ID</label>
                  <input
                    className="form-input"
                    type="text"
                    value={modalGroupId}
                    onChange={(e) => setModalGroupId(e.target.value)}
                    placeholder="输入分组ID"
                  />
                </div>
              )}

              <div className="form-group">
                <label className="form-label required">分组名称</label>
                <input
                  className="form-input"
                  type="text"
                  value={modalGroupName}
                  onChange={(e) => setModalGroupName(e.target.value)}
                  placeholder="输入分组名称"
                />
              </div>

              <div className="form-group">
                <label className="form-label">股票列表</label>
                {modalSymbols.map((sym, i) => (
                  <div className="symbol-row" key={i}>
                    <input
                      className="form-input code-input"
                      type="text"
                      value={sym.code}
                      onChange={(e) => {
                        setModalSymbols((prev) => {
                          const next = [...prev]
                          next[i] = { ...next[i], code: e.target.value }
                          return next
                        })
                      }}
                      placeholder="股票代码"
                    />
                    <input
                      className="form-input"
                      type="text"
                      value={sym.name}
                      onChange={(e) => {
                        setModalSymbols((prev) => {
                          const next = [...prev]
                          next[i] = { ...next[i], name: e.target.value }
                          return next
                        })
                      }}
                      placeholder="股票名称"
                    />
                    <button
                      className="btn-icon danger remove-symbol-btn"
                      type="button"
                      onClick={() =>
                        setModalSymbols((prev) => prev.filter((_, idx) => idx !== i))
                      }
                    >
                      <span className="sr-only">移除</span>
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  className="btn btn-secondary btn-sm"
                  type="button"
                  style={{ marginTop: 8 }}
                  onClick={() =>
                    setModalSymbols((prev) => [...prev, { code: '', name: '' }])
                  }
                >
                  添加股票
                </button>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                type="button"
                onClick={closeModal}
              >
                取消
              </button>
              <button
                className="btn btn-primary"
                type="button"
                disabled={modalSaving}
                onClick={handleSave}
              >
                {modalSaving ? '保存中...' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Groups
