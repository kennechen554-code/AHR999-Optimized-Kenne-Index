import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { KeyRound, ShieldCheck } from 'lucide-react'
import { disableMfa, enableMfa, setupMfa } from '../services/api'
import type { UserInfo } from '../types/api'

export default function MfaPage() {
  const { user } = useOutletContext<{ user: UserInfo | null }>()
  const [secret, setSecret] = useState('')
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [confirmCode, setConfirmCode] = useState('')
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)

  const start = async () => {
    try {
      const result = await setupMfa()
      setSecret(result.secret)
      setMessage('请将 secret 添加到认证器应用后输入 6 位验证码。')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '生成 Secret 失败')
    }
  }

  const enable = async () => {
    try {
      const result = await enableMfa(secret, code)
      setMessage(`MFA 已启用。备份码: ${result.backup_codes.join(', ')}`)
      setSecret('')
      setCode('')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '启用 MFA 失败')
    }
  }

  const disable = async () => {
    if (user?.mfa_enabled && !showConfirm) {
      setShowConfirm(true)
      setMessage('停用 MFA 需要二次身份验证，请在下方输入当前 6 位验证码确认。')
      return
    }
    setLoading(true)
    try {
      const result = await disableMfa(confirmCode)
      setMessage(result.message)
      setShowConfirm(false)
      setConfirmCode('')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '停用失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <section className="standard-panel p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-1 text-green" size={22} />
          <div>
            <div className="section-kicker">MFA</div>
            <h2 className="section-title">多因素认证与 Step-up</h2>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              启用后，实盘执行、API Key 更新、角色变更、租户风控和删除确认等敏感操作需要额外验证码。
            </p>
          </div>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="metric-tile">
          <span>当前状态</span>
          <strong>{user?.mfa_enabled ? '已启用' : '未启用'}</strong>
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          <button onClick={start} className="secondary-button px-4 py-3">
            <KeyRound size={15} />
            生成 TOTP Secret
          </button>
          {user?.mfa_enabled ? (
            <button onClick={disable} disabled={loading} className="danger-button">
              {showConfirm ? '确认停用' : '停用 MFA'}
            </button>
          ) : (
            <button onClick={disable} disabled={loading} className="secondary-button px-4 py-3">
              停用 MFA
            </button>
          )}
        </div>
        {showConfirm && (
          <div className="mt-5 grid gap-3 max-w-md">
            <input
              className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white"
              value={confirmCode}
              onChange={(event) => setConfirmCode(event.target.value)}
              placeholder="请输入当前 6 位 MFA 验证码"
              maxLength={6}
            />
            <button
              onClick={() => { setShowConfirm(false); setConfirmCode(''); setMessage('') }}
              className="secondary-button w-fit px-5 py-2 text-xs"
            >
              取消
            </button>
          </div>
        )}
        {secret && (
          <div className="mt-5 grid gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 font-mono text-sm">{secret}</div>
            <input className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm" value={code} onChange={(event) => setCode(event.target.value)} placeholder="6 位验证码" />
            <button onClick={enable} disabled={!code} className="primary-button w-fit px-5 py-3 disabled:opacity-50">启用 MFA</button>
          </div>
        )}
      </section>

      {message && <div className="rounded-2xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">{message}</div>}
    </div>
  )
}
