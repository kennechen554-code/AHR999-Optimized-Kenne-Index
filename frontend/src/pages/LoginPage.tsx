import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ArrowRight, CheckCircle2, Lock, Mail, ShieldCheck, User, WalletCards, Gift } from 'lucide-react'
import BrandWordmark from '../components/BrandWordmark'
import { forgotPassword, login, register, resetPassword } from '../services/api'
import type { UserInfo } from '../types/api'

interface LoginPageProps {
  onLogin: () => Promise<UserInfo>
}

function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const initialResetToken = new URLSearchParams(location.search).get('reset_token') || ''
  const initialCode = new URLSearchParams(location.search).get('code') || ''
  const initialAction = new URLSearchParams(location.search).get('action') || ''
  
  const [mode, setMode] = useState<'login' | 'register'>(initialAction === 'register' ? 'register' : 'login')
  const [resetToken, setResetToken] = useState(initialResetToken)
  const [resetMode, setResetMode] = useState(Boolean(initialResetToken))
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const [referralCode, setReferralCode] = useState(initialCode)



  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        if (!acceptedTerms) {
          setError('您必须同意用户服务协议与隐私政策才能注册')
          setLoading(false)
          return
        }
        await register(email, password, name, acceptedTerms, referralCode)
      }
      await onLogin()
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname
      navigate(from || (mode === 'register' ? '/app/onboarding' : '/app/dashboard'), { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async () => {
    setError('')
    if (!email) {
      setError('请先输入邮箱地址')
      return
    }
    setLoading(true)
    try {
      const result = await forgotPassword(email)
      setError(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (event: React.FormEvent) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await resetPassword(resetToken, password)
      setError(result.message)
      setResetMode(false)
      setMode('login')
      setPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : '密码重置失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-shell min-h-screen bg-bg px-4 py-10 text-text-primary">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.035),transparent_360px)]" />
      <div className="relative grid w-full max-w-6xl gap-6 lg:grid-cols-[minmax(0,1fr)_440px]">
        <section className="login-hero-panel hidden p-7 lg:block">
          <Link to="/" className="flex items-center">
            <BrandWordmark caption="Professional DCA Desk" compact />
          </Link>
          <div className="mt-16 max-w-lg">
            <h1 className="text-5xl font-semibold leading-tight">进入你的加密资产 DCA 控制台</h1>
            <p className="mt-5 text-base leading-7 text-text-secondary">
              用一套一致的风险语言管理估值、动量、预算和执行权限。默认模拟盘，Premium 实盘二次确认。
            </p>
          </div>
          <div className="login-preview">
            {[
              ['BTC', '0.4621', '低估区'],
              ['ETH', '0.8348', '定投区'],
              ['SOL', '1.1820', '观察区'],
            ].map(([symbol, ki, zone]) => (
              <div key={symbol} className="asset-row">
                <div>
                  <div className="text-sm font-semibold">{symbol}</div>
                  <div className="text-[11px] text-text-tertiary">{zone}</div>
                </div>
                <div className="font-mono text-lg">{ki}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="login-card surface-enter p-6">
          <Link to="/" className="mb-7 flex items-center justify-center lg:hidden">
            <BrandWordmark caption="专业 DCA 工作台" compact />
          </Link>
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/12 text-accent">
              <WalletCards size={20} />
            </div>
            <div>
              <h1 className="text-xl font-semibold">{resetMode ? '重置密码' : mode === 'login' ? '登录工作台' : '创建账户'}</h1>
              <p className="text-sm text-text-secondary">访问你的信号、预算和订阅权限</p>
            </div>
          </div>

          {!resetMode && <div className="mb-5 grid grid-cols-2 rounded-lg border border-white/10 bg-white/[0.03] p-1">
            {(['login', 'register'] as const).map((item) => (
              <button
                key={item}
                onClick={() => { setMode(item); setError('') }}
                className={`rounded-md py-2 text-sm font-medium transition ${mode === item ? 'bg-white/10 text-white' : 'text-text-secondary hover:text-white'}`}
              >
                {item === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>}

          <form onSubmit={resetMode ? handleResetPassword : handleSubmit} className="space-y-4">
            {resetMode && (
              <label className="form-field">
                <Lock size={16} />
                <input
                  placeholder="重置令牌"
                  value={resetToken}
                  onChange={(event) => setResetToken(event.target.value)}
                  required
                />
              </label>
            )}
            {!resetMode && mode === 'register' && (
              <label className="form-field">
                <User size={16} />
                <input
                  type="text"
                  placeholder="显示名称"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
            )}

            {!resetMode && mode === 'register' && (
              <label className="form-field">
                <Gift size={16} className="text-accent" />
                <input
                  type="text"
                  placeholder="邀请码（可选）"
                  value={referralCode}
                  onChange={(event) => setReferralCode(event.target.value)}
                />
              </label>
            )}

            {!resetMode && <label className="form-field">
              <Mail size={16} />
              <input
                type="email"
                placeholder="邮箱地址"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>}

            <label className="form-field">
              <Lock size={16} />
              <input
                type="password"
                placeholder="密码（至少 8 位）"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
              />
            </label>

            {mode === 'register' && !resetMode && (
              <label className="flex items-start gap-2 text-xs text-text-secondary cursor-pointer select-none py-1">
                <input
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(event) => setAcceptedTerms(event.target.checked)}
                  className="mt-0.5 rounded border-white/10 bg-white/[0.04] text-accent focus:ring-accent"
                />
                <span>
                  我已阅读并同意 <Link to="/terms" target="_blank" className="text-accent hover:underline">《服务条款》</Link> 与 <Link to="/privacy" target="_blank" className="text-accent hover:underline">《隐私政策》</Link>
                </span>
              </label>
            )}

            {error && <div className="rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red">{error}</div>}

            <button
              type="submit"
              disabled={loading || (mode === 'register' && !resetMode && !acceptedTerms)}
              className="primary-button w-full justify-center py-3 disabled:opacity-40"
            >
              {loading ? '处理中' : resetMode ? '重置密码' : mode === 'login' ? '登录' : '创建账户'}
              <ArrowRight size={16} />
            </button>
          </form>
          {!resetMode && mode === 'login' && (
            <button
              type="button"
              className="mt-3 text-sm font-semibold text-accent hover:text-white"
              onClick={handleForgotPassword}
              disabled={loading}
            >
              忘记密码
            </button>
          )}
          {resetMode && (
            <button
              type="button"
              className="mt-3 text-sm font-semibold text-accent hover:text-white"
              onClick={() => setResetMode(false)}
            >
              返回登录
            </button>
          )}
          <div className="mt-5 grid gap-2 text-xs text-text-tertiary">
            <div className="flex items-center gap-2"><ShieldCheck size={14} className="text-green" /> HttpOnly Cookie + JWT 会话</div>
            <div className="flex items-center gap-2"><CheckCircle2 size={14} className="text-green" /> API Key 服务端加密保存</div>
          </div>
          {/* Removed duplicate static legal terms note to make space for the interactive checkbox */}
        </section>
      </div>
    </div>
  )
}

export default LoginPage
