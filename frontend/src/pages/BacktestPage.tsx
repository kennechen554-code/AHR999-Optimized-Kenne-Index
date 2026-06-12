import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, CheckCircle2, Database, FileUp, LockKeyhole, Play, ShieldAlert } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchBacktestStrategies, fetchLocalBacktestDatasets, runCustomBacktest } from '../services/api'
import type { BacktestResult, LocalDataset, StrategyMetadata, StrategyMode, UserInfo } from '../types/api'

type DataSourceMode = 'upload' | 'server'
type SymbolCode = 'BTC' | 'ETH' | 'SOL'

const SYMBOLS: SymbolCode[] = ['BTC', 'ETH', 'SOL']

const FALLBACK_STRATEGIES: StrategyMetadata[] = [
  {
    mode: 'per_asset_strict_dd',
    label: '严格回撤版',
    default: true,
    risk_level: '稳健',
    description: '默认实盘策略。优先控制最大回撤，保留现金缓冲，只在高置信估值区间释放更多预算。',
    reserve_frac: 0.08,
    reserve_release_score: 5.612096,
    assets: [],
  },
  {
    mode: 'per_asset_balanced_return',
    label: '收益优先版',
    default: false,
    risk_level: '进取',
    description: '收益与资金利用率优先。提高资金部署弹性，适合愿意承受更深回撤的回测分析。',
    reserve_frac: 0,
    reserve_release_score: 4.680613,
    assets: [],
  },
]

function currency(value: number) {
  return value.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: value > 1000 ? 0 : 2 })
}

function percent(value: number) {
  return `${(value * 100).toFixed(2)}%`
}

function datasetUpdatedAt(dataset: LocalDataset) {
  if (!dataset.updated_at) return '未检测到文件'
  return new Date(dataset.updated_at * 1000).toLocaleString('zh-CN', { hour12: false })
}

function BacktestPage() {
  const { user } = useOutletContext<{ user: UserInfo | null }>()
  const isPremium = Boolean(user?.entitlements.backtesting || user?.plan === 'premium')
  const [sourceMode, setSourceMode] = useState<DataSourceMode>('server')
  const [files, setFiles] = useState<File[]>([])
  const [strategyMode, setStrategyMode] = useState<StrategyMode>('per_asset_strict_dd')
  const [startDate, setStartDate] = useState('2018-07-20')
  const [endDate, setEndDate] = useState('2026-02-24')
  const [monthlyBudget, setMonthlyBudget] = useState(700)
  const [serverPaths, setServerPaths] = useState<Record<SymbolCode, string>>({ BTC: '', ETH: '', SOL: '' })
  const [pathsInitialized, setPathsInitialized] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { data: strategyResult } = useQuery({
    queryKey: ['backtest-strategies'],
    queryFn: fetchBacktestStrategies,
  })
  const { data: localDatasets } = useQuery({
    queryKey: ['backtest-local-datasets'],
    queryFn: fetchLocalBacktestDatasets,
    enabled: isPremium,
    retry: false,
  })

  const strategies = strategyResult?.strategies.length ? strategyResult.strategies : FALLBACK_STRATEGIES
  const activeStrategy = strategies.find((item) => item.mode === strategyMode) || strategies[0]

  useEffect(() => {
    if (!localDatasets?.datasets.length || pathsInitialized) return
    const nextPaths = { BTC: '', ETH: '', SOL: '' }
    localDatasets.datasets.forEach((dataset) => {
      if (SYMBOLS.includes(dataset.symbol as SymbolCode) && dataset.exists) {
        nextPaths[dataset.symbol as SymbolCode] = dataset.path
      }
    })
    setServerPaths(nextPaths)
    setPathsInitialized(true)
  }, [localDatasets, pathsInitialized])

  const selectedDatasetCount = useMemo(
    () => SYMBOLS.filter((symbol) => serverPaths[symbol].trim()).length,
    [serverPaths],
  )

  const deployRows = useMemo(() => {
    if (!result) return []
    return Object.entries(result.deploy_weights).map(([symbol, weight]) => ({ symbol, weight }))
  }, [result])

  const runBacktest = async () => {
    if (!isPremium) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      if (sourceMode === 'upload' && files.length === 0) {
        throw new Error('请至少选择一个 BTC、ETH 或 SOL CSV 文件')
      }
      if (sourceMode === 'server' && selectedDatasetCount === 0) {
        throw new Error('请至少填写一个允许目录内的服务器 CSV 路径')
      }
      const response = await runCustomBacktest({
        strategy_mode: strategyMode,
        start_date: startDate,
        end_date: endDate,
        monthly_budget: monthlyBudget,
        files: sourceMode === 'upload' ? files : [],
        server_paths: sourceMode === 'server' ? serverPaths : undefined,
      })
      setResult(response.data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '回测失败')
    } finally {
      setLoading(false)
    }
  }

  if (!isPremium) {
    return (
      <div className="space-y-5">
        <section className="standard-panel surface-enter p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-3xl">
              <div className="section-kicker">Premium Backtest</div>
              <h2 className="section-title">自定义回测需要高级会员</h2>
              <p className="mt-3 text-sm leading-6 text-text-secondary">
                回测会读取上传 CSV 或服务器本地 CSV，并运行完整 per-asset 策略计算。为避免策略参数、路径读取和结果解释被滥用，该能力仅对 Premium 开放。
              </p>
            </div>
            <div className="glass-control flex items-center gap-3 px-4 py-3">
              <LockKeyhole className="text-orange" size={20} />
              <div>
                <div className="text-sm font-semibold">Premium Locked</div>
                <div className="text-xs text-text-tertiary">回测、实盘、报告能力</div>
              </div>
            </div>
          </div>
          <div className="mt-6 grid gap-3 md:grid-cols-3">
            {['上传 BTC/ETH/SOL CSV', '读取允许目录本地数据', '生成权益与回撤曲线'].map((item) => (
              <div key={item} className="metric-tile">
                <span>{item}</span>
                <LockKeyhole size={15} className="text-orange" />
              </div>
            ))}
          </div>
          <Link to="/app/billing" className="primary-button mt-6 w-fit px-5 py-3">
            查看 Premium 权益
          </Link>
        </section>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <section className="standard-panel surface-enter p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="section-kicker">Backtest Lab</div>
            <h2 className="section-title">Premium 自定义回测</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
              使用上传 CSV 或服务器白名单目录内的本地 CSV，临时运行后端真实策略逻辑。上传文件和路径不会持久化保存。
            </p>
          </div>
          <div className="glass-tabs w-fit">
            {[
              ['server', '服务器路径'],
              ['upload', '上传 CSV'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setSourceMode(value as DataSourceMode)}
                className={`glass-tab ${sourceMode === value ? 'glass-tab-active' : ''}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_390px]">
        <div className="standard-panel p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="section-kicker">Strategy Source</div>
              <h3 className="text-base font-semibold">策略模式</h3>
            </div>
            <div className="glass-tabs w-fit">
              {strategies.map((strategy) => (
                <button
                  key={strategy.mode}
                  type="button"
                  onClick={() => setStrategyMode(strategy.mode)}
                  className={`glass-tab ${strategyMode === strategy.mode ? 'glass-tab-active' : ''}`}
                >
                  {strategy.label}
                </button>
              ))}
            </div>
          </div>
          <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <BarChart3 size={18} className="text-accent" />
                  <span className="font-semibold">{activeStrategy.label}</span>
                  {activeStrategy.default && <span className="status-pill status-basic">默认</span>}
                </div>
                <p className="mt-2 text-sm leading-6 text-text-secondary">{activeStrategy.description}</p>
              </div>
              <div className="status-pill status-premium">{activeStrategy.risk_level}</div>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {activeStrategy.assets.map((asset) => (
                <div key={asset.symbol} className="metric-tile">
                  <span>{asset.symbol} · {asset.interval_days} 天周期</span>
                  <strong>{(asset.budget_weight * 100).toFixed(1)}%</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="standard-panel p-5">
          <div className="section-kicker">Parameters</div>
          <h3 className="text-base font-semibold">回测参数</h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <label className="field-block">
              <span>开始日期</span>
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label className="field-block">
              <span>结束日期</span>
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            </label>
            <label className="field-block">
              <span>月预算 USDT</span>
              <input type="number" value={monthlyBudget} onChange={(event) => setMonthlyBudget(Number(event.target.value))} />
            </label>
          </div>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="mb-4 flex items-center gap-2">
          {sourceMode === 'server' ? <Database size={18} className="text-accent" /> : <FileUp size={18} className="text-accent" />}
          <h3 className="text-base font-semibold">{sourceMode === 'server' ? '服务器本地 CSV' : '浏览器上传 CSV'}</h3>
        </div>

        {sourceMode === 'server' ? (
          <div className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-3">
              {SYMBOLS.map((symbol) => (
                <label key={symbol} className="field-block">
                  <span>{symbol} CSV 路径</span>
                  <input
                    value={serverPaths[symbol]}
                    onChange={(event) => setServerPaths((prev) => ({ ...prev, [symbol]: event.target.value }))}
                    placeholder={`${symbol}=backend/data/...csv`}
                  />
                </label>
              ))}
            </div>
            <div className="rounded-lg border border-white/10 bg-black/10 p-4">
              <div className="mb-3 text-sm font-semibold">内置数据集状态</div>
              <div className="grid gap-2 lg:grid-cols-3">
                {(localDatasets?.datasets || []).map((dataset) => (
                  <div key={dataset.symbol} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold">{dataset.symbol}</span>
                      <span className={`status-pill ${dataset.exists ? 'status-premium' : 'status-basic'}`}>
                        {dataset.exists ? '可用' : '缺失'}
                      </span>
                    </div>
                    <div className="mt-2 truncate font-mono text-[11px] text-text-tertiary" title={dataset.path}>{dataset.path}</div>
                    <div className="mt-2 text-[11px] text-text-tertiary">{datasetUpdatedAt(dataset)}</div>
                  </div>
                ))}
              </div>
              <div className="mt-3 text-xs leading-5 text-text-tertiary">
                允许目录：{localDatasets?.allowed_dirs.join('；') || '读取中'}。后端会校验 resolve 后路径必须位于允许目录内。
              </div>
            </div>
          </div>
        ) : (
          <div>
            <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-white/20 bg-black/10 px-4 py-6 text-center transition hover:border-accent/50 hover:bg-accent/5">
              <FileUp size={26} className="text-accent" />
              <span className="mt-2 text-sm font-semibold">选择 BTC / ETH / SOL CSV</span>
              <span className="mt-1 text-xs text-text-tertiary">文件名需包含 BTC、ETH 或 SOL；文件只用于本次临时计算。</span>
              <input
                className="hidden"
                type="file"
                accept=".csv,text/csv"
                multiple
                onChange={(event) => setFiles(Array.from(event.target.files || []))}
              />
            </label>
            <div className="mt-3 flex flex-wrap gap-2">
              {files.length ? files.map((file) => (
                <span key={file.name} className="status-pill status-basic">{file.name}</span>
              )) : <span className="text-xs text-text-tertiary">尚未选择文件</span>}
            </div>
          </div>
        )}

        {error && <div className="mt-4 rounded-lg border border-red/30 bg-red/10 px-4 py-3 text-sm text-red">{error}</div>}

        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2 text-xs leading-5 text-text-tertiary">
            <ShieldAlert size={15} className="mt-0.5 shrink-0 text-orange" />
            回测结果依赖历史 CSV 完整性、日期范围和策略版本，不代表未来收益。
          </div>
          <button type="button" onClick={runBacktest} disabled={loading} className="primary-button justify-center px-5 py-3 disabled:opacity-50">
            <Play size={16} />
            {loading ? '回测中' : '运行回测'}
          </button>
        </div>
      </section>

      {result && (
        <section className="standard-panel p-5">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="section-kicker">Backtest Result</div>
              <h3 className="text-base font-semibold">{result.strategy_label} · {result.start} 至 {result.end}</h3>
            </div>
            <div className="status-pill status-premium">
              <CheckCircle2 size={14} />
              计算完成
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              {[
                ['期末权益', currency(result.final_equity)],
                ['累计投入', currency(result.total_contrib)],
                ['总收益率', percent(result.total_return)],
                ['XIRR 年化', percent(result.xirr)],
                ['最大回撤', percent(result.max_drawdown)],
                ['现金结余', currency(result.cash_end)],
                ['交易次数', String(result.trades)],
                ['资金利用率', percent(result.avg_utilization)],
              ].map(([label, value]) => (
                <div key={label} className="metric-tile">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
            <div className="h-80 rounded-lg border border-white/10 bg-black/10 p-3">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={result.series}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} />
                  <YAxis yAxisId="left" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} width={52} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} width={42} />
                  <Tooltip contentStyle={{ background: '#111316', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8 }} />
                  <Line yAxisId="left" type="monotone" dataKey="equity" name="权益" stroke="#0a84ff" dot={false} strokeWidth={2} />
                  <Line yAxisId="right" type="monotone" dataKey="drawdown" name="回撤" stroke="#ff453a" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            {deployRows.map((row) => (
              <div key={row.symbol} className="metric-tile">
                <span>{row.symbol} 部署权重</span>
                <strong>{percent(row.weight)}</strong>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

export default BacktestPage
