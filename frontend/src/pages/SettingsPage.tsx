import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bell, Building2, KeyRound, Lock, Play, RotateCw, Save, ShieldCheck, SlidersHorizontal, UserRound } from 'lucide-react'
import {
  changePassword,
  fetchBacktestStrategies,
  fetchConfig,
  fetchExchanges,
  fetchSessions,
  fetchTaskRuns,
  fetchTaskStatus,
  resendVerificationEmail,
  revokeSession,
  runAutomationNow,
  saveConfig,
  testEmail,
  updateTask,
} from '../services/api'
import type { UserConfig, UserInfo } from '../types/api'
import TaskRunTimeline from '../components/TaskRunTimeline'

const DEFAULT_CONFIG: UserConfig = {
  exchange: 'okx',
  api_key: '',
  api_secret: '',
  api_passphrase: '',
  simulated: true,
  budget_mode: 'MONTHLY',
  budget_amount: 700,
  run_interval_days: 7,
  strategy_mode: 'per_asset_strict_dd',
  smtp_host: 'smtp.gmail.com',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  email_to: '',
  notifications_enabled: false,
  notify_on_execution: true,
  notify_on_budget: true,
  notify_on_error: true,
  automation_enabled: false,
  automation_market_data: false,
  automation_dry_run: false,
  automation_live_enabled: false,
}

const PASSPHRASE_EXCHANGES = ['okx', 'bitget', 'kucoin']
const SMTP_HOSTS: Record<string, number> = {
  'smtp.gmail.com': 587,
  'smtp.qq.com': 465,
  'smtp.163.com': 465,
  'smtp-mail.outlook.com': 587,
}

function SettingsPage() {
  const { user } = useOutletContext<{ user: UserInfo | null }>()
  const [config, setConfig] = useState<UserConfig>(DEFAULT_CONFIG)
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current_password: '', new_password: '' })

  const { data: strategyResult } = useQuery({
    queryKey: ['backtest-strategies'],
    queryFn: fetchBacktestStrategies,
  })
  const { data: exchanges = {} } = useQuery({
    queryKey: ['exchanges'],
    queryFn: fetchExchanges,
  })
  const configQuery = useQuery({
    queryKey: ['config-settings'],
    queryFn: fetchConfig,
  })
  const taskStatus = useQuery({
    queryKey: ['task-status'],
    queryFn: fetchTaskStatus,
  })
  const taskRuns = useQuery({
    queryKey: ['task-runs'],
    queryFn: () => fetchTaskRuns(1),
  })
  const sessionsQuery = useQuery({
    queryKey: ['sessions'],
    queryFn: fetchSessions,
  })

  useEffect(() => {
    if (configQuery.data) {
      setConfig(configQuery.data)
    }
  }, [configQuery.data])

  const perRunEstimate = config.budget_mode === 'FIXED'
    ? config.budget_amount
    : config.budget_amount / Math.max(1, 30 / config.run_interval_days)
  const activeStrategy = strategyResult?.strategies.find((strategy) => strategy.mode === config.strategy_mode)
  const supportedExchangeCount = user?.entitlements.supported_exchanges.length || Object.keys(exchanges).length
  const update = (fields: Partial<UserConfig>) => setConfig((prev) => ({ ...prev, ...fields }))

  const connectedState = useMemo(() => {
    if (!config.api_key || config.api_key.includes('****')) return '已保存或待验证'
    return '待保存验证'
  }, [config.api_key])

  const handleSave = async () => {
    if (config.budget_amount <= 0) {
      setStatus({ ok: false, msg: '预算金额必须大于 0' })
      return
    }
    if (config.run_interval_days < 1 || config.run_interval_days > 30) {
      setStatus({ ok: false, msg: '执行间隔必须在 1 到 30 天之间' })
      return
    }
    if (config.email_to && !config.email_to.includes('@')) {
      setStatus({ ok: false, msg: '收件人邮箱格式无效' })
      return
    }
    if (config.smtp_port <= 0 || config.smtp_port > 65535) {
      setStatus({ ok: false, msg: 'SMTP 端口无效' })
      return
    }
    setLoading(true)
    setStatus(null)
    try {
      const result = await saveConfig(config)
      setStatus({ ok: result.ok, msg: result.message })
      await configQuery.refetch()
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '保存失败' })
    } finally {
      setLoading(false)
    }
  }

  const handleChangePassword = async () => {
    if (!passwordForm.current_password || passwordForm.new_password.length < 8) {
      setStatus({ ok: false, msg: '请输入当前密码，新密码至少 8 位' })
      return
    }
    setLoading(true)
    try {
      const result = await changePassword(passwordForm)
      setPasswordForm({ current_password: '', new_password: '' })
      setStatus({ ok: result.ok, msg: result.message })
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '密码修改失败' })
    } finally {
      setLoading(false)
    }
  }

  const handleTestEmail = async () => {
    setLoading(true)
    try {
      const result = await testEmail()
      setStatus({ ok: result.ok, msg: result.message })
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '测试邮件发送失败' })
    } finally {
      setLoading(false)
    }
  }

  const handleRunAutomation = async () => {
    setLoading(true)
    try {
      const result = await runAutomationNow()
      setStatus({ ok: result.ok, msg: result.message })
      await taskStatus.refetch()
      await taskRuns.refetch()
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '自动化任务执行失败' })
    } finally {
      setLoading(false)
    }
  }

  const handleResendVerification = async () => {
    setLoading(true)
    try {
      const result = await resendVerificationEmail()
      setStatus({ ok: result.ok, msg: result.message })
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '验证邮件发送失败' })
    } finally {
      setLoading(false)
    }
  }

  const handleRevokeSession = async (sessionId: string) => {
    setLoading(true)
    try {
      const result = await revokeSession(sessionId)
      setStatus({ ok: result.ok, msg: result.message })
      await sessionsQuery.refetch()
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '会话撤销失败' })
    } finally {
      setLoading(false)
    }
  }

  const handleToggleTask = async (taskId: number, enabled: boolean) => {
    setLoading(true)
    try {
      const result = await updateTask(taskId, { enabled })
      setStatus({ ok: result.ok, msg: '任务配置已更新' })
      await taskStatus.refetch()
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '任务配置更新失败' })
    } finally {
      setLoading(false)
    }
  }

  const reload = async () => {
    try {
      const result = await configQuery.refetch()
      if (result.data) setConfig(result.data)
      setStatus({ ok: true, msg: '配置已重新加载' })
    } catch (err) {
      setStatus({ ok: false, msg: err instanceof Error ? err.message : '配置加载失败' })
    }
  }

  return (
    <div className="space-y-5">
      <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="standard-panel surface-enter p-6">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-3xl border border-white/10 bg-white/[0.08]">
                <UserRound size={26} className="text-accent" />
              </div>
              <div>
                <div className="section-kicker">Account Management</div>
                <h2 className="section-title">{user?.display_name || 'Kenne User'}</h2>
                <p className="mt-2 text-sm text-text-secondary">{user?.email}</p>
              </div>
            </div>
            <span className={`status-pill ${user?.plan === 'premium' ? 'status-premium' : 'status-basic'}`}>
              {user?.plan || 'free'} · {user?.subscription_status || 'none'}
            </span>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {[
              ['租户', user?.tenant?.name || '个人工作区'],
              ['支持交易所', `${supportedExchangeCount} 家`],
              ['回测权限', user?.entitlements.backtesting ? '已解锁' : 'Premium 专属'],
              ['邮箱验证', user?.email_verified ? '已验证' : '待验证'],
            ].map(([label, value]) => (
              <div key={label} className="metric-tile">
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          {!user?.email_verified && (
            <button onClick={handleResendVerification} disabled={loading} className="secondary-button mt-4 px-4 py-3 disabled:opacity-50">
              <ShieldCheck size={16} />
              重发验证邮件
            </button>
          )}
        </div>

        <div className="standard-panel p-6">
          <div className="flex items-center gap-3">
            <SlidersHorizontal size={22} className="text-accent" />
            <div>
              <div className="section-kicker">Active Strategy</div>
              <h2 className="section-title">{activeStrategy?.label || '策略加载中'}</h2>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-text-secondary">
            {activeStrategy?.description || '策略选项来自后端 /api/v1/backtest/strategies，避免出现前后端参数说明不一致。'}
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="metric-tile">
              <span>单次预算估算</span>
              <strong>${perRunEstimate.toFixed(2)}</strong>
            </div>
            <div className="metric-tile">
              <span>现金保留</span>
              <strong>{activeStrategy ? `${(activeStrategy.reserve_frac * 100).toFixed(1)}%` : '-'}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="mb-4 flex items-center gap-3">
          <Building2 size={20} className="text-accent" />
          <div>
            <div className="section-kicker">Exchange Connection</div>
            <h3 className="text-base font-semibold">交易所连接</h3>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="field-block">
            <span>交易所</span>
            <select value={config.exchange} onChange={(event) => update({ exchange: event.target.value })}>
              {Object.entries(exchanges).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select>
          </label>
          <label className="field-block">
            <span>执行环境</span>
            <button
              type="button"
              onClick={() => update({ simulated: !config.simulated })}
              className={`toggle-button ${config.simulated ? 'toggle-on' : ''}`}
            >
              <span />
              {config.simulated ? '模拟盘优先' : '实盘配置'}
            </button>
          </label>
          <label className="field-block">
            <span>API Key</span>
            <input type="password" value={config.api_key} onChange={(event) => update({ api_key: event.target.value })} />
          </label>
          <label className="field-block">
            <span>API Secret</span>
            <input type="password" value={config.api_secret} onChange={(event) => update({ api_secret: event.target.value })} />
          </label>
          {PASSPHRASE_EXCHANGES.includes(config.exchange) && (
            <label className="field-block md:col-span-2">
              <span>Passphrase</span>
              <input type="password" value={config.api_passphrase} onChange={(event) => update({ api_passphrase: event.target.value })} />
            </label>
          )}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            ['连接状态', connectedState],
            ['权限建议', '禁用提现、使用子账户、绑定 IP 白名单'],
            ['密钥存储', '服务端加密保存，前端返回掩码'],
          ].map(([label, value]) => (
            <div key={label} className="standard-panel p-4 flex flex-col gap-1 hover:transform-none">
              <span className="text-xs text-text-tertiary">{label}</span>
              <strong className="text-sm font-semibold text-text-primary leading-5">{value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center gap-3">
            <Play size={20} className="text-accent" />
            <div>
              <div className="section-kicker">Automation</div>
              <h3 className="text-base font-semibold">自动化任务</h3>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ['automation_enabled', '启用自动化总开关'],
              ['automation_market_data', '定时更新行情'],
              ['automation_dry_run', '定时模拟执行'],
              ['automation_live_enabled', '预留自动实盘'],
            ].map(([key, label]) => (
              <label key={key} className="metric-tile cursor-pointer">
                <span>{label}</span>
                <input
                  type="checkbox"
                  checked={Boolean(config[key as keyof UserConfig])}
                  onChange={(event) => update({ [key]: event.target.checked } as Partial<UserConfig>)}
                />
              </label>
            ))}
          </div>
          <div className="mt-4 rounded-2xl border border-orange/25 bg-orange/10 p-3 text-xs leading-5 text-orange">
            自动实盘为预留字段，不会自动下实盘单。后端当前禁止启用 automation_live 任务，第一版只开放手动触发自动化 dry-run。
          </div>
          <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-xs leading-5 text-text-secondary">
            交易所 API Key 建议使用独立子账户，只开放现货交易权限，禁用提现，绑定服务器出口 IP，并定期轮换密钥。
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="metric-tile">
              <span>任务状态</span>
              <strong>{taskStatus.data?.running ? '运行中' : '空闲'}</strong>
            </div>
            <div className="metric-tile">
              <span>最近结果</span>
              <strong>{taskStatus.data?.last_message || taskStatus.data?.last_error || '-'}</strong>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {(taskStatus.data?.tasks || []).map((task) => (
              <div key={task.id} className="metric-tile">
                <span>{task.task_type} · {task.interval_minutes} 分钟</span>
                <div className="flex items-center gap-3">
                  <strong>{task.enabled ? '已启用' : '已暂停'}</strong>
                  <input
                    type="checkbox"
                    checked={task.enabled}
                    disabled={loading || !user?.entitlements.automation || task.task_type === 'automation_live'}
                    onChange={(event) => handleToggleTask(task.id, event.target.checked)}
                  />
                </div>
              </div>
            ))}
          </div>
          <button onClick={handleRunAutomation} disabled={loading || !user?.entitlements.automation} className="secondary-button mt-4 px-4 py-3 disabled:opacity-50">
            <Play size={16} />
            立即运行 dry-run
          </button>
          <div className="mt-5 border-t border-white/10 pt-5">
            <div className="section-kicker">Recent Runs</div>
            <h4 className="mt-1 text-sm font-semibold">自动化运行历史</h4>
            <div className="mt-3">
              <TaskRunTimeline runs={taskRuns.data?.records || taskStatus.data?.recent_runs || []} />
            </div>
          </div>
        </div>

        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center gap-3">
            <Lock size={20} className="text-accent" />
            <div>
              <div className="section-kicker">Security</div>
              <h3 className="text-base font-semibold">账户安全</h3>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="field-block">
              <span>当前密码</span>
              <input
                type="password"
                value={passwordForm.current_password}
                onChange={(event) => setPasswordForm((prev) => ({ ...prev, current_password: event.target.value }))}
              />
            </label>
            <label className="field-block">
              <span>新密码</span>
              <input
                type="password"
                value={passwordForm.new_password}
                onChange={(event) => setPasswordForm((prev) => ({ ...prev, new_password: event.target.value }))}
              />
            </label>
          </div>
          <button onClick={handleChangePassword} disabled={loading} className="secondary-button mt-4 px-4 py-3 disabled:opacity-50">
            <Lock size={16} />
            修改密码
          </button>
          <div className="mt-6 border-t border-white/10 pt-5">
            <div className="section-kicker">Sessions</div>
            <h4 className="mt-1 text-sm font-semibold">登录设备</h4>
            <div className="mt-3 space-y-2">
              {(sessionsQuery.data?.sessions || []).length === 0 ? (
                <div className="text-sm text-text-tertiary">暂无会话记录</div>
              ) : sessionsQuery.data?.sessions.map((session) => (
                <div key={session.session_id} className="metric-tile">
                  <span className="truncate">{session.ip_address || 'unknown'} · {session.user_agent || 'unknown'}</span>
                  <button
                    className="secondary-button px-3 py-2 text-xs"
                    disabled={loading || session.is_current}
                    onClick={() => handleRevokeSession(session.session_id)}
                  >
                    {session.is_current ? '当前会话' : '撤销'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center gap-3">
            <KeyRound size={20} className="text-accent" />
            <div>
              <div className="section-kicker">DCA Discipline</div>
              <h3 className="text-base font-semibold">策略与预算纪律</h3>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-4">
            <label className="field-block">
              <span>策略模式</span>
              <select
                value={config.strategy_mode}
                onChange={(event) => update({ strategy_mode: event.target.value as UserConfig['strategy_mode'] })}
              >
                {(strategyResult?.strategies || [
                  { mode: 'per_asset_strict_dd', label: '严格回撤版' },
                  { mode: 'per_asset_balanced_return', label: '收益优先版' },
                ]).map((strategy) => (
                  <option key={strategy.mode} value={strategy.mode}>{strategy.label}</option>
                ))}
              </select>
            </label>
            <label className="field-block">
              <span>预算模式</span>
              <select value={config.budget_mode} onChange={(event) => update({ budget_mode: event.target.value })}>
                <option value="MONTHLY">月度预算</option>
                <option value="FIXED">单次固定</option>
              </select>
            </label>
            <label className="field-block">
              <span>{config.budget_mode === 'MONTHLY' ? '月度预算 USDT' : '单次金额 USDT'}</span>
              <input type="number" value={config.budget_amount} onChange={(event) => update({ budget_amount: Number(event.target.value) })} />
            </label>
            <label className="field-block">
              <span>执行间隔</span>
              <select value={config.run_interval_days} onChange={(event) => update({ run_interval_days: Number(event.target.value) })}>
                {[1, 3, 7, 14, 30].map((day) => <option key={day} value={day}>{day} 天</option>)}
              </select>
            </label>
          </div>
          {activeStrategy && (
            <div className="mt-4 rounded-3xl border border-white/10 bg-white/[0.035] p-4">
              <div className="text-sm font-semibold">{activeStrategy.label} · {activeStrategy.risk_level}</div>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{activeStrategy.description}</p>
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {activeStrategy.assets.map((asset) => (
                  <div key={asset.symbol} className="metric-tile">
                    <span>{asset.symbol} · {asset.interval_days} 天</span>
                    <strong>{(asset.budget_weight * 100).toFixed(1)}%</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="standard-panel p-5">
          <div className="section-kicker">Risk Preference</div>
          <h3 className="text-base font-semibold">风险偏好与执行模式</h3>
          <div className="mt-4 space-y-3">
            {[
              ['默认执行', config.simulated ? '模拟盘优先' : '实盘配置'],
              ['实盘闸门', user?.entitlements.live_trading ? 'Premium 已解锁' : '未解锁'],
              ['二次确认', '每次实盘执行必须确认'],
              ['回测权限', user?.entitlements.backtesting ? '可运行' : 'Premium 专属'],
            ].map(([label, value]) => (
              <div key={label} className="metric-tile">
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="mb-4 flex items-center gap-3">
          <Bell size={20} className="text-accent" />
          <div>
            <div className="section-kicker">Notifications</div>
            <h3 className="text-base font-semibold">通知配置</h3>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="field-block md:col-span-2">
            <span>通知总开关</span>
            <button
              type="button"
              onClick={() => update({ notifications_enabled: !config.notifications_enabled })}
              className={`toggle-button ${config.notifications_enabled ? 'toggle-on' : ''}`}
            >
              <span />
              {config.notifications_enabled ? '已启用通知' : '未启用通知'}
            </button>
          </label>
          <label className="field-block">
            <span>SMTP 主机</span>
            <select
              value={Object.keys(SMTP_HOSTS).includes(config.smtp_host) ? config.smtp_host : 'smtp.gmail.com'}
              onChange={(event) => {
                const host = event.target.value
                update({ smtp_host: host, smtp_port: SMTP_HOSTS[host] })
              }}
            >
              {Object.keys(SMTP_HOSTS).map((host) => <option key={host} value={host}>{host}</option>)}
            </select>
          </label>
          <label className="field-block">
            <span>端口</span>
            <input type="number" value={config.smtp_port} onChange={(event) => update({ smtp_port: Number(event.target.value) })} />
          </label>
          <label className="field-block">
            <span>邮箱账号</span>
            <input value={config.smtp_user} onChange={(event) => update({ smtp_user: event.target.value })} />
          </label>
          <label className="field-block">
            <span>邮箱密码</span>
            <input type="password" value={config.smtp_password} onChange={(event) => update({ smtp_password: event.target.value })} />
          </label>
          <label className="field-block md:col-span-2">
            <span>收件人</span>
            <input type="email" value={config.email_to} onChange={(event) => update({ email_to: event.target.value })} />
          </label>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            ['notify_on_execution', '执行报告'],
            ['notify_on_budget', '预算提醒'],
            ['notify_on_error', '异常告警'],
          ].map(([key, label]) => (
            <label key={key} className="metric-tile cursor-pointer">
              <span>{label}</span>
              <input
                type="checkbox"
                checked={Boolean(config[key as keyof UserConfig])}
                onChange={(event) => update({ [key]: event.target.checked } as Partial<UserConfig>)}
              />
            </label>
          ))}
        </div>
        <button onClick={handleTestEmail} disabled={loading || !config.notifications_enabled} className="secondary-button mt-4 px-4 py-3 disabled:opacity-50">
          <Bell size={16} />
          发送测试邮件
        </button>
      </section>

      <div className="flex flex-wrap gap-3">
        <button onClick={handleSave} disabled={loading} className="primary-button px-5 py-3 disabled:opacity-50">
          <Save size={16} />
          {loading ? '保存中' : '保存设置'}
        </button>
        <button onClick={reload} className="secondary-button px-5 py-3">
          <RotateCw size={16} />
          重新加载
        </button>
      </div>

      {status && (
        <div className={`flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm ${status.ok ? 'border-green/30 bg-green/10 text-green' : 'border-red/30 bg-red/10 text-red'}`}>
          <ShieldCheck size={16} />
          {status.msg}
        </div>
      )}
    </div>
  )
}

export default SettingsPage
