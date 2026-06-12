import { useState } from 'react'
import { Download, ShieldAlert, Trash2 } from 'lucide-react'
import { confirmAccountDeletion, historyExportUrl, operationAuditExportUrl, requestAccountDeletion } from '../services/api'

function download(url: string) {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = ''
  anchor.click()
}

export default function DataRightsPage() {
  const [message, setMessage] = useState('')
  const [token, setToken] = useState('')
  const [stepUpCode, setStepUpCode] = useState('')

  const requestDeletion = async () => {
    const result = await requestAccountDeletion()
    setMessage(result.token && import.meta.env.DEV ? `${result.message} 本地 token: ${result.token}` : result.message)
    if (result.token) setToken(result.token)
  }

  const confirmDeletion = async () => {
    const result = await confirmAccountDeletion(token, stepUpCode)
    setMessage(result.message)
  }

  return (
    <div className="space-y-5">
      <section className="standard-panel p-5">
        <div className="section-kicker">Data Rights</div>
        <h2 className="section-title">数据导出与账号删除</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
          导出能力不会包含交易所 API Key、SMTP 密码或内部密钥。账号删除先进入确认流程，确认后禁用账号并撤销会话。
        </p>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="standard-panel p-5">
          <Download size={20} className="text-accent" />
          <h3 className="mt-3 text-base font-semibold">导出数据</h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">下载全量交易审计 CSV 和操作审计 CSV，用于合规留存或迁移。</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button onClick={() => download(historyExportUrl())} className="secondary-button px-4 py-3">导出全部交易</button>
            <button onClick={() => download(operationAuditExportUrl())} className="secondary-button px-4 py-3">导出操作审计</button>
          </div>
        </div>

        <div className="standard-panel border-orange/30 p-5">
          <ShieldAlert size={20} className="text-orange" />
          <h3 className="mt-3 text-base font-semibold">账号删除请求</h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">删除请求确认后会禁用账号并撤销所有会话。租户 OWNER 删除前应先处理团队所有权。</p>
          <button onClick={requestDeletion} className="danger-button mt-5">
            <Trash2 size={14} />
            请求删除账号
          </button>
          <div className="mt-4 grid gap-3">
            <input className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm" value={token} onChange={(event) => setToken(event.target.value)} placeholder="删除确认 token" />
            <input className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm" value={stepUpCode} onChange={(event) => setStepUpCode(event.target.value)} placeholder="MFA step-up code (if enabled)" />
            <button onClick={confirmDeletion} disabled={!token} className="secondary-button px-4 py-3 disabled:opacity-50">确认删除请求</button>
          </div>
        </div>
      </section>

      {message && <div className="rounded-2xl border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">{message}</div>}
    </div>
  )
}
