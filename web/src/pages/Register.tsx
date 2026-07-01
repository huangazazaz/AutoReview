import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useApp } from '@/hooks/useApp'

export default function Register() {
  const { register } = useAuth()
  const { showToast } = useApp()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    // Frontend validation
    if (!username.trim()) {
      showToast('请输入用户名', 'warning')
      return
    }
    if (username.trim().length < 2) {
      showToast('用户名至少需要2个字符', 'warning')
      return
    }
    if (!password) {
      showToast('请输入密码', 'warning')
      return
    }
    if (password.length < 4) {
      showToast('密码至少需要4个字符', 'warning')
      return
    }
    if (password !== confirmPassword) {
      showToast('两次输入的密码不一致', 'warning')
      return
    }

    setLoading(true)
    try {
      await register(username.trim(), password)
      showToast('注册成功！', 'success')
      navigate('/')
    } catch (err) {
      showToast((err as Error).message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-card__header">
          <h1 className="auth-card__title">BacktestLab</h1>
          <p className="auth-card__subtitle">创建新账户</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-card__form">
          <div className="form-group">
            <label className="form-label" htmlFor="reg-username">用户名</label>
            <input
              id="reg-username"
              className="form-input"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="2-64个字符"
              autoComplete="username"
              autoFocus
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="reg-password">密码</label>
            <input
              id="reg-password"
              className="form-input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="至少4个字符"
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="reg-confirm">确认密码</label>
            <input
              id="reg-confirm"
              className="form-input"
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="再次输入密码"
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary auth-card__submit"
            disabled={loading}
          >
            {loading ? '注册中...' : '注 册'}
          </button>
        </form>

        <div className="auth-card__footer">
          <span>已有账号？</span>
          <Link to="/login" className="auth-card__link">立即登录</Link>
        </div>
      </div>
    </div>
  )
}
