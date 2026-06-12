import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, CreditCard, Database, Loader2, Play, ShieldCheck, Wallet, XCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { fetchBacktestStrategies, fetchBalance, fetchConfig, fetchMe, fetchTradingPreflight, runDca, updateMarketData } from '../services/api'

interface LogEntry {
  msg: string
  type: 'success' | 'error' | 'info'
  ts: string
}

function ExecutePage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [balances, setBalances] = useState<Record<string, { free: number; used: number; total: number }> | null>(null)
  const [busy, setBusy] = useState('')
  const [confirmLive, setConfirmLive] = useState(false)
  const [lastResult, setLastResult] = useState<{ ok: boolean; total: number; mode: string } | null>(null)
  const { data: user } = useQuery({ queryKey: ['me'], queryFn: fetchMe })
  const { data: config } = useQuery({ queryKey: ['config-execute'], queryFn: fetchConfig })
  const { data: strategies } = useQuery({ queryKey: ['backtest-strategies'], queryFn: fetchBacktestStrategies })
  const preflight = useQuery({ queryKey: ['trading-preflight'], queryFn: fetchTradingPreflight })

  const liveUnlocked = Boolean(user?.entitlements.live_trading)
  const liveCap = Number(user?.entitlements.max_live_order_usdt || 0)
  const activeStrategy = strategies?.strategies.find((strategy) => strategy.mode === config?.strategy_mode)
  const now = () => new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const log = (msg: string, type: LogEntry['type'] = 'info') => setLogs((prev) => [{ msg, type, ts: now() }, ...prev])

  const handleUpdateData = async () => {
    setBusy('data')
    setLogs([])
    log('正在拉取交易所 4H K 线数据')
    try {
      const results = await updateMarketData()
      results.forEach((item) => {
        if (item.error) log(`${item.symbol}: ${item.error}`, 'error')
        else log(`${item.symbol}: ${item.source || '行情源'} 新增 ${item.added || 0} 条 K 线`, 'success')
      })
    } catch (err) {
      log(err instanceof Error ? err.message : '行情更新失败', 'error')
    } finally {
      setBusy('')
    }
  }

  const handleBalance = async () => {
    setBusy('balance')
    setLogs([])
    try {
      const data = await fetchBalance()
      setBalances(data)
      log(`资产查询成功，共 ${Object.keys(data).length} 个币种`, 'success')
    } catch (err) {
      log(err instanceof Error ? err.message : '资产查询失败', 'error')
    } finally {
      setBusy('')
    }
  }

  const handleDca = async (dryRun: boolean) => {
    setBusy(dryRun ? 'dry' : 'live')
    setLogs([])
    setLastResult(null)
    log(dryRun ? '开始模拟执行，不会产生真实订单' : '提交实盘执行请求')
    try {
      const result = await runDca(dryRun, !dryRun && confirmLive)
      result.orders.forEach((order) => {
        const status = String(order.status || '')
        const ok = status === 'filled' || status === 'dry_run'
        log(`${String(order.symbol)} · $${Number(order.usdt || 0).toFixed(2)} · ${status.toUpperCase()}`, ok ? 'success' : 'error')
      })
      log(result.message || '执行完成', result.ok ? 'success' : 'info')
      setLastResult({ ok: result.ok, total: result.total_usdt, mode: result.mode })
      await preflight.refetch()
    } catch (err) {
      log(err instanceof Error ? err.message : '执行失败', 'error')
      setLastResult({ ok: false, total: 0, mode: dryRun ? 'dry_run' : 'live' })
    } finally {
      setBusy('')
    }
  }

  const actions = [
    { id: 'data', title: '更新行情数据', desc: '刷新 BTC / ETH / SOL 的本地 K 线数据。', icon: Database, onClick: handleUpdateData },
    { id: 'balance', title: '查询交易所资产', desc: '使用已配置 API Key 读取账户余额。', icon: Wallet, onClick: handleBalance },
    { id: 'dry', title: '模拟执行 DCA', desc: '按当前信号分配预算，不触发真实订单。', icon: Play, onClick: () => handleDca(true) },
  ]

  return (
    <div className="space-y-5">
      <section className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="standard-panel p-5">
          <div className="section-kicker">Execution</div>
          <h2 className="section-title">手动执行中心</h2>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            执行链路按“行情更新、信号计算、预算分配、订单提交”推进。模拟盘用于验证策略，实盘交易仅对 Premium 开放。
          </p>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {[
              ['当前策略', activeStrategy?.label || '加载中'],
              ['预算模式', config?.budget_mode === 'FIXED' ? '单次固定' : '月度预算'],
              ['执行环境', config?.simulated ? '模拟盘优先' : '实盘配置'],
              ['实盘单次上限', liveCap > 0 ? `$${liveCap.toFixed(0)} USDT` : '未解锁'],
            ].map(([label, value]) => (
              <div key={label} className="metric-tile">
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {actions.map(({ id, title, desc, icon: Icon, onClick }) => (
              <button key={id} onClick={onClick} disabled={!!busy} className="action-tile text-left disabled:opacity-50">
                <Icon size={20} className="text-accent" />
                <span className="mt-3 block text-sm font-semibold">{title}</span>
                <span className="mt-1 block text-xs leading-5 text-text-secondary">{desc}</span>
                {busy === id && <Loader2 size={15} className="mt-3 animate-spin text-accent" />}
              </button>
            ))}
          </div>
        </div>

        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <AlertTriangle size={18} className={liveUnlocked ? 'text-orange' : 'text-gray'} />
            <h3 className="text-base font-semibold">实盘交易闸门</h3>
          </div>
          <div className={`rounded-lg border p-3 text-sm ${liveUnlocked ? 'border-orange/30 bg-orange/10 text-orange' : 'border-white/10 bg-white/[0.03] text-text-secondary'}`}>
            {liveUnlocked ? `Premium 已解锁实盘能力。单次上限 ${liveCap.toFixed(0)} USDT，每次执行仍需要二次确认。` : '当前套餐未解锁实盘交易，只能使用模拟执行。'}
          </div>
          {!liveUnlocked && (
            <Link to="/app/billing" className="secondary-button mt-4 w-full justify-center py-3">
              <CreditCard size={15} />
              查看 Premium 实盘方案
            </Link>
          )}
          <label className="mt-4 flex items-start gap-3 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={confirmLive}
              disabled={!liveUnlocked}
              onChange={(event) => setConfirmLive(event.target.checked)}
              className="mt-1"
            />
            我确认本次实盘执行将使用真实资金，并已检查 API 权限、预算和交易所账户。
          </label>
          <button
            onClick={() => handleDca(false)}
            disabled={!liveUnlocked || !confirmLive || !!busy}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-red px-4 py-3 text-sm font-semibold text-white transition hover:bg-red/90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy === 'live' ? <Loader2 size={15} className="animate-spin" /> : <ShieldCheck size={16} />}
            提交实盘执行
          </button>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="section-kicker">Live Preflight</div>
            <h3 className="text-base font-semibold">实盘前预检</h3>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              聚合邮箱验证、交易所支持、API Key、余额读取、预算、全局/租户实盘开关和行情数据新鲜度。
            </p>
          </div>
          <button onClick={() => preflight.refetch()} className="secondary-button px-4 py-3 text-sm">
            重新预检
          </button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {(preflight.data?.checks || []).map((check) => (
            <div key={check.key} className="metric-tile">
              <span>{check.message}</span>
              <strong className={check.ok ? 'text-green' : 'text-orange'}>{check.ok ? '通过' : '需处理'}</strong>
            </div>
          ))}
          {!preflight.data && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-text-secondary md:col-span-3">
              {preflight.isLoading ? '预检加载中' : '暂无预检结果，请点击重新预检。'}
            </div>
          )}
        </div>
        {preflight.data && (
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <div className="metric-tile"><span>实盘剩余额度</span><strong>${preflight.data.budget.remaining_live.toFixed(2)}</strong></div>
            <div className="metric-tile"><span>余额读取</span><strong>{preflight.data.balance.status}</strong></div>
            <div className="metric-tile"><span>租户急停</span><strong>{preflight.data.live.tenant_paused ? '已暂停' : '未暂停'}</strong></div>
            <div className="metric-tile"><span>全局实盘</span><strong>{preflight.data.live.global_enabled ? '开启' : '关闭'}</strong></div>
          </div>
        )}
      </section>

      {lastResult && (
        <section className={`standard-panel flex items-center gap-3 p-4 ${lastResult.ok ? 'border-green/30' : 'border-red/30'}`}>
          {lastResult.ok ? <CheckCircle2 className="text-green" /> : <XCircle className="text-red" />}
          <div>
            <div className="text-sm font-semibold">{lastResult.ok ? '执行完成' : '执行失败'}</div>
            <div className="text-xs text-text-secondary">模式 {lastResult.mode} · 总投入 ${lastResult.total.toFixed(2)} USDT</div>
          </div>
        </section>
      )}

      {balances && (
        <section className="standard-panel p-5">
          <h3 className="mb-3 text-base font-semibold">账户资产</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {Object.entries(balances).map(([symbol, balance]) => (
              <div key={symbol} className="metric-tile">
                <span>{symbol}</span>
                <strong>{balance.free.toFixed(4)}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      {logs.length > 0 && (
        <section className="standard-panel overflow-hidden">
          <div className="border-b border-white/10 px-5 py-3 text-sm font-semibold">执行日志</div>
          <div className="max-h-64 space-y-1 overflow-y-auto p-4 font-mono text-xs">
            {logs.map((entry, index) => (
              <div key={`${entry.ts}-${index}`} className={entry.type === 'success' ? 'text-green' : entry.type === 'error' ? 'text-red' : 'text-accent'}>
                <span className="mr-2 text-text-tertiary">{entry.ts}</span>
                {entry.msg}
              </div>
            ))}
          </div>
        </section>
      )}
      {logs.length === 0 && (
        <section className="standard-panel p-5 text-sm leading-6 text-text-secondary">
          暂无执行日志。你可以先更新行情数据或运行模拟执行，确认订单审计和预算结果后再考虑实盘。
        </section>
      )}
    </div>
  )
}

export default ExecutePage
