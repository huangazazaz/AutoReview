import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: number
  msg: string
  type: ToastType
}

interface AppContextValue {
  showToast: (msg: string, type?: ToastType) => void
  loading: boolean
  loadingMsg: string
  showLoading: (msg?: string) => void
  hideLoading: () => void
  showModal: (title: string, body: ReactNode, footer?: ReactNode) => Promise<boolean>
  showConfirm: (msg: string) => Promise<boolean>
}

const AppCtx = createContext<AppContextValue>(null!)

let toastId = 0
let modalResolve: ((v: boolean) => void) | null = null

export function AppProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState('加载中...')
  const [modal, setModal] = useState<{ title: string; body: ReactNode; footer?: ReactNode } | null>(null)

  const showToast = useCallback((msg: string, type: ToastType = 'info') => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }, [])

  const showLoadingFn = useCallback((msg = '加载中...') => {
    setLoadingMsg(msg)
    setLoading(true)
  }, [])

  const hideLoadingFn = useCallback(() => {
    setLoading(false)
  }, [])

  const showModalFn = useCallback((title: string, body: ReactNode, footer?: ReactNode) => {
    return new Promise<boolean>((resolve) => {
      modalResolve = resolve
      setModal({ title, body, footer })
    })
  }, [])

  const closeModal = useCallback((confirmed: boolean) => {
    setModal(null)
    if (modalResolve) {
      modalResolve(confirmed)
      modalResolve = null
    }
  }, [])

  const showConfirmFn = useCallback((msg: string) => {
    return showModalFn('确认操作',
      <p style={{ color: 'var(--text-secondary)' }}>{msg}</p>,
      <>
        <button className="btn btn-secondary" onClick={() => closeModal(false)}>取消</button>
        <button className="btn btn-danger" onClick={() => closeModal(true)}>确认</button>
      </>
    )
  }, [showModalFn, closeModal])

  const ctx: AppContextValue = {
    showToast,
    loading,
    loadingMsg,
    showLoading: showLoadingFn,
    hideLoading: hideLoadingFn,
    showModal: showModalFn,
    showConfirm: showConfirmFn,
  }

  return (
    <AppCtx.Provider value={ctx}>
      {children}

      {/* Toast 容器 */}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map(t => (
            <div key={t.id} className={`toast toast-${t.type}`}>
              <span className="toast-icon">
                {t.type === 'success' ? svgCheck : t.type === 'error' ? svgX : t.type === 'warning' ? svgAlert : svgInfo}
              </span>
              <span>{t.msg}</span>
            </div>
          ))}
        </div>
      )}

      {/* 加载遮罩 */}
      {loading && (
        <div className="loading-overlay" style={{ display: 'flex' }}>
          <div className="spinner" />
          <p>{loadingMsg}</p>
        </div>
      )}

      {/* 模态框 */}
      {modal && (
        <div className="modal-overlay" onClick={() => closeModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">{modal.title}</span>
              <button className="modal-close" onClick={() => closeModal(false)}>&times;</button>
            </div>
            <div className="modal-body">{modal.body}</div>
            {modal.footer && <div className="modal-footer">{modal.footer}</div>}
          </div>
        </div>
      )}
    </AppCtx.Provider>
  )
}

export function useApp() {
  return useContext(AppCtx)
}

// 内联 SVG 图标
const svgCheck = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)
const svgX = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
  </svg>
)
const svgAlert = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
    <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
)
const svgInfo = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
  </svg>
)
