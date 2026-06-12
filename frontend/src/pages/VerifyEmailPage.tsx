import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { CheckCircle2, Loader2, Mail, XCircle, ArrowRight } from 'lucide-react'
import BrandWordmark from '../components/BrandWordmark'
import { useAuth } from '../hooks/useAuth'
import { verifyEmail } from '../services/api'

export default function VerifyEmailPage() {
  const location = useLocation()
  const token = new URLSearchParams(location.search).get('token') || ''
  const { authed } = useAuth()

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage('无效的验证链接：缺失安全令牌。')
      return
    }

    verifyEmail(token)
      .then((result) => {
        setStatus('success')
        setMessage(result.message || '电子邮箱验证成功！')
      })
      .catch((err: unknown) => {
        setStatus('error')
        setMessage(err instanceof Error ? err.message : '邮箱验证失败，链接可能已过期。')
      })
  }, [token])

  return (
    <div className="login-shell min-h-screen bg-bg px-4 py-10 text-text-primary flex items-center justify-center">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.035),transparent_360px)]" />
      <div className="relative w-full max-w-md surface-enter p-6 rounded-3xl border border-white/10 bg-[#1e2024]">
        <div className="mb-7 flex items-center justify-center">
          <BrandWordmark caption="专业 DCA 工作台" compact />
        </div>

        <div className="flex flex-col items-center text-center">
          {status === 'loading' && (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent mb-4">
                <Loader2 size={24} className="animate-spin" />
              </div>
              <h1 className="text-xl font-semibold">正在验证邮箱</h1>
              <p className="mt-2 text-sm text-text-secondary leading-6">正在向安全服务器校验您的验证令牌，请稍候...</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-green/10 text-green mb-4">
                <CheckCircle2 size={24} />
              </div>
              <h1 className="text-xl font-semibold">验证成功</h1>
              <p className="mt-2 text-sm text-text-secondary leading-6">{message}</p>
              
              <Link
                to={authed ? "/app/dashboard" : "/login"}
                className="primary-button mt-6 w-full justify-center py-3"
              >
                {authed ? '进入投资工作台' : '去登录'}
                <ArrowRight size={16} />
              </Link>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red/10 text-red mb-4">
                <XCircle size={24} />
              </div>
              <h1 className="text-xl font-semibold">验证失败</h1>
              <p className="mt-2 text-sm text-red leading-6">{message}</p>

              <Link
                to="/login"
                className="secondary-button mt-6 w-full justify-center py-3"
              >
                <Mail size={15} />
                返回登录页面
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
