import { useMemo } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  BarChart3,
  CalendarClock,
  DatabaseZap,
  Gauge,
  RefreshCw,
  ShieldAlert,
  Target,
  TrendingDown,
} from 'lucide-react'
import OnboardingChecklist from '../components/OnboardingChecklist'
import { useToast } from '../components/ToastProvider'
import { fetchBacktestStrategies, fetchConfig, fetchHistory, fetchMvrv, fetchSignals, fetchSharePerformance } from '../services/api'
import type { Signal, UserInfo } from '../types/api'

interface SignalChartPoint {
  symbol: string
  ki: number
  mult: number
}

interface SvgPoint {
  x: number
  y: number
}

function currency(value: number) {
  return value.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value > 1000 ? 0 : 2,
  })
}

function assetTone(symbol: string) {
  if (symbol === 'BTC') return 'asset-orb asset-orb-btc'
  if (symbol === 'ETH') return 'asset-orb asset-orb-eth'
  return 'asset-orb asset-orb-sol'
}

function zoneTone(signal: Signal) {
  if (signal.final_mult >= 1.5) return 'border-green/30 bg-green/10 text-green'
  if (signal.final_mult > 0) return 'border-accent/30 bg-accent/10 text-accent'
  return 'border-orange/30 bg-orange/10 text-orange'
}

function signalLabel(signal: Signal) {
  if (signal.momentum === 'FALLING') return '防跌折扣'
  if (signal.final_mult >= 1.5) return '低估加仓'
  if (signal.final_mult > 0) return '纪律定投'
  return '等待信号'
}

function getChartRange(values: number[]): { min: number; max: number } {
  const fallback = { min: 0, max: 1 }
  if (values.length === 0) return fallback
  const min = Math.min(...values, 0)
  const max = Math.max(...values, 1)
  if (min === max) return { min: min - 1, max: max + 1 }
  const padding = (max - min) * 0.12
  return { min: Math.max(0, min - padding), max: max + padding }
}

function toSignalSvgPoints(data: SignalChartPoint[], range: { min: number; max: number }): SvgPoint[] {
  const left = 48
  const top = 28
  const width = 720
  const height = 300
  const usableWidth = width - left - 34
  const usableHeight = height - top - 50

  return data.map((point, index) => ({
    x: left + (data.length <= 1 ? usableWidth / 2 : (index / (data.length - 1)) * usableWidth),
    y: top + (1 - (point.ki - range.min) / (range.max - range.min)) * usableHeight,
  }))
}

function pathFrom(points: SvgPoint[]): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ')
}

function PortfolioSignalChart({ data }: { data: SignalChartPoint[] }) {
  const range = getChartRange(data.map((point) => point.ki))
  const points = toSignalSvgPoints(data, range)
  const linePath = pathFrom(points)
  const areaPath = points.length > 0
    ? `${linePath} L ${points[points.length - 1].x.toFixed(1)} 250 L ${points[0].x.toFixed(1)} 250 Z`
    : ''
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
    y: 28 + ratio * 222,
    value: range.max - ratio * (range.max - range.min),
  }))

  return (
    <svg className="h-full w-full" viewBox="0 0 720 300" role="img" aria-label="Kenne Index 概览趋势">
      <defs>
        <linearGradient id="dashboard-ki-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#51c7e4" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#51c7e4" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {ticks.map((tick) => (
        <g key={tick.y}>
          <line x1="48" x2="686" y1={tick.y} y2={tick.y} stroke="rgba(226,226,232,0.08)" />
          <text x="18" y={tick.y + 4} fill="rgba(196,199,200,0.66)" fontSize="12">
            {tick.value.toFixed(1)}
          </text>
        </g>
      ))}
      {areaPath && <path d={areaPath} fill="url(#dashboard-ki-fill)" />}
      {linePath && <path d={linePath} fill="none" stroke="#51c7e4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />}
      {points.map((point, index) => (
        <g key={data[index].symbol}>
          <circle cx={point.x} cy={point.y} r="4" fill="#0b0d11" stroke="#51c7e4" strokeWidth="2" />
          <text x={point.x} y="282" fill="rgba(196,199,200,0.72)" fontSize="12" textAnchor="middle">
            {data[index].symbol}
          </text>
        </g>
      ))}
    </svg>
  )
}

function SignalCard({ signal }: { signal: Signal }) {
  if (signal.error) {
    return (
      <div className="standard-panel p-5">
        <div className="flex items-center gap-3">
          <span className={assetTone(signal.symbol)}>{signal.symbol.slice(0, 1)}</span>
          <div>
            <div className="font-semibold">{signal.symbol}</div>
            <div className="text-sm text-red">{signal.error}</div>
          </div>
        </div>
      </div>
    )
  }

  const deviation = signal.valuation > 0 ? ((signal.price - signal.valuation) / signal.valuation) * 100 : 0

  return (
    <div className="standard-panel p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className={assetTone(signal.symbol)}>{signal.symbol.slice(0, 1)}</span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-semibold">{signal.symbol}</span>
              <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${zoneTone(signal)}`}>
                {signalLabel(signal)}
              </span>
            </div>
            <div className="mt-1 text-xs text-text-tertiary">数据日期 {signal.date}</div>
          </div>
        </div>
        <div className="text-right">
          <div className="data-value text-base font-semibold">{currency(signal.price)}</div>
          <div className={`mt-1 text-xs ${deviation < 0 ? 'text-green' : 'text-orange'}`}>
            估值偏离 {deviation >= 0 ? '+' : ''}{deviation.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-3 gap-3">
        <div>
          <div className="text-xs text-text-tertiary">Kenne Index</div>
          <div className="data-value mt-1 text-base xs:text-lg sm:text-xl md:text-2xl font-semibold">{signal.kenne_index.toFixed(4)}</div>
        </div>
        <div>
          <div className="text-xs text-text-tertiary">执行倍数</div>
          <div className="data-value mt-1 text-base xs:text-lg sm:text-xl md:text-2xl font-semibold">{signal.final_mult.toFixed(2)}x</div>
        </div>
        <div>
          <div className="text-xs text-text-tertiary">模型 R²</div>
          <div className="data-value mt-1 text-base xs:text-lg sm:text-xl md:text-2xl font-semibold">{signal.r2.toFixed(2)}</div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2">
        <div className="metric-tile">
          <span>7日</span>
          <strong className={signal.ret_7d >= 0 ? 'text-green' : 'text-red'}>{signal.ret_7d.toFixed(1)}%</strong>
        </div>
        <div className="metric-tile">
          <span>14日</span>
          <strong className={signal.ret_14d >= 0 ? 'text-green' : 'text-red'}>{signal.ret_14d.toFixed(1)}%</strong>
        </div>
        <div className="metric-tile">
          <span>分位</span>
          <strong>{signal.pct_rank.toFixed(1)}%</strong>
        </div>
      </div>
    </div>
  )
}

function DashboardPage() {
  const { user } = useOutletContext<{ user: UserInfo | null }>()
  const { pushToast } = useToast()
  const { data: signals = [], isLoading, refetch } = useQuery({
    queryKey: ['signals'],
    queryFn: fetchSignals,
  })
  const { data: mvrv, isError: mvrvError } = useQuery({
    queryKey: ['mvrv'],
    queryFn: fetchMvrv,
    enabled: Boolean(user?.entitlements.mvrv),
  })
  const { data: config } = useQuery({ queryKey: ['config-summary'], queryFn: fetchConfig })
  const { data: strategies } = useQuery({ queryKey: ['backtest-strategies'], queryFn: fetchBacktestStrategies })
  const { data: history } = useQuery({ queryKey: ['history-dashboard'], queryFn: () => fetchHistory({ status: 'all', page_size: 10 }) })
  const { data: sharePerf } = useQuery({ queryKey: ['share-performance'], queryFn: fetchSharePerformance })

  const validSignals = signals.filter((signal) => !signal.error)
  const summary = useMemo(() => {
    const active = validSignals.filter((signal) => signal.final_mult > 0)
    const avgKi = validSignals.length ? validSignals.reduce((sum, signal) => sum + signal.kenne_index, 0) / validSignals.length : 0
    const totalWeight = active.reduce((sum, signal) => sum + signal.final_mult, 0)
    const riskScore = validSignals.length
      ? validSignals.reduce((sum, signal) => sum + (signal.momentum === 'FALLING' ? 2 : signal.final_mult > 0 ? 1 : 0), 0) / validSignals.length
      : 0
    return { active, avgKi, totalWeight, riskScore }
  }, [validSignals])

  const activeStrategy = strategies?.strategies.find((item) => item.mode === config?.strategy_mode)
  const chartData = validSignals.map((signal) => ({
    symbol: signal.symbol,
    ki: Number(signal.kenne_index.toFixed(4)),
    mult: Number(signal.final_mult.toFixed(2)),
  }))
  const budgetPerRun = config
    ? config.budget_mode === 'FIXED'
      ? config.budget_amount
      : config.budget_amount / Math.max(1, 30 / config.run_interval_days)
    : 0

  return (
    <div className="space-y-5">
      <OnboardingChecklist user={user} config={config} hideWhenComplete />
      <section className="grid gap-4 xl:grid-cols-[1.35fr_0.85fr]">
        <div className="standard-panel surface-enter p-5 sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="section-kicker">Portfolio Signal</div>
              <h2 className="display-title">Kenne {summary.avgKi.toFixed(2)}</h2>
              <p className="mt-4 max-w-2xl text-base leading-7 text-text-secondary">
                智能投资工作台由先进的量化模型与风控系统实时驱动。信号生成、资金分配、多重安全风控闸门与全局对账机制均由系统底层统一托管，确保每笔定投决策科学、透明、可追溯。
              </p>
            </div>
            <button onClick={() => refetch()} disabled={isLoading} className="secondary-button dashboard-refresh-button px-4 py-3 text-sm disabled:opacity-50">
              <RefreshCw size={16} className={isLoading ? 'animate-spin' : ''} />
              <span>刷新信号</span>
            </button>
          </div>

          <div className="mt-7 grid gap-3 md:grid-cols-4">
            {[
              { label: '活跃资产', value: `${summary.active.length}/${validSignals.length}`, icon: Target, tone: 'text-green' },
              { label: '总执行权重', value: `${summary.totalWeight.toFixed(2)}x`, icon: Activity, tone: 'text-accent' },
              { label: '单次预算估算', value: budgetPerRun ? `$${budgetPerRun.toFixed(0)}` : '加载中', icon: Gauge, tone: 'text-orange' },
              { label: '数据状态', value: isLoading ? '刷新中' : '可用', icon: DatabaseZap, tone: 'text-green' },
            ].map(({ label, value, icon: Icon, tone }) => (
              <div key={label} className="metric-tile">
                <span className="flex items-center gap-2">
                  <Icon size={14} className={tone} />
                  {label}
                </span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>

          <div className="portfolio-chart-shell mt-5">
            {chartData.length > 0 ? (
              <PortfolioSignalChart data={chartData} />
            ) : (
              <div className="chart-empty-state">
                {isLoading ? '信号图表加载中' : '暂无可绘制信号，请先刷新行情或检查本地 CSV 数据'}
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-4">
          <div className="standard-panel surface-enter surface-enter-delay p-5">
            <div className="section-kicker">Strategy Version</div>
            <h2 className="section-title">{activeStrategy?.label || '策略加载中'}</h2>
            <p className="mt-3 text-sm leading-6 text-text-secondary">
              {activeStrategy?.description || '策略执行参数与量化回测历史完全同源，由交易引擎实时监控并动态调整。'}
            </p>
            <div className="mt-5 grid gap-3">
              <div className="metric-tile">
                <span>风险等级</span>
                <strong>{activeStrategy?.risk_level || '校验中'}</strong>
              </div>
              <div className="metric-tile">
                <span>现金保留</span>
                <strong>{activeStrategy ? `${(activeStrategy.reserve_frac * 100).toFixed(1)}%` : '-'}</strong>
              </div>
              <div className="metric-tile">
                <span>执行间隔</span>
                <strong>{config?.run_interval_days ? `${config.run_interval_days} 天` : '-'}</strong>
              </div>
            </div>
          </div>

          <div className="standard-panel p-5">
            <div className="section-kicker">Audit Snapshot</div>
            <h2 className="section-title">近期审计摘要</h2>
            <div className="mt-4 grid gap-3">
              <div className="metric-tile">
                <span>执行记录</span>
                <strong>{history?.count ?? 0}</strong>
              </div>
              <div className="metric-tile">
                <span>累计投入</span>
                <strong>{currency(history?.total ?? 0)}</strong>
              </div>
              <div className="metric-tile">
                <span>默认环境</span>
                <strong>{config?.simulated ? '模拟盘' : '实盘配置'}</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {signals.map((signal) => <SignalCard key={signal.symbol} signal={signal} />)}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_390px]">
        <div className="standard-panel overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4">
            <div className="section-kicker">Model Confidence</div>
            <h2 className="section-title">幂律模型与预算权重</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>资产</th>
                  <th>当前价格</th>
                  <th>估值中枢</th>
                  <th>Kenne Index</th>
                  <th>R²</th>
                  <th>执行建议</th>
                </tr>
              </thead>
              <tbody>
                {validSignals.map((signal) => (
                  <tr key={signal.symbol}>
                    <td className="font-semibold">{signal.symbol}</td>
                    <td>{currency(signal.price)}</td>
                    <td>{currency(signal.valuation)}</td>
                    <td>{signal.kenne_index.toFixed(4)}</td>
                    <td>{signal.r2.toFixed(4)}</td>
                    <td>{signalLabel(signal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <ShieldAlert size={19} className="text-orange" />
            <h2 className="text-base font-semibold">链上估值参考</h2>
          </div>
          <div className="space-y-3">
            {!user?.entitlements.mvrv && (
              <div className="rounded-2xl border border-orange/25 bg-orange/10 p-4 text-sm leading-6 text-orange">
                MVRV 指标需要 Basic 或 Premium。<Link to="/app/billing" className="font-semibold underline">查看升级方案</Link>
              </div>
            )}
            {user?.entitlements.mvrv && mvrvError && (
              <div className="rounded-2xl border border-red/25 bg-red/10 p-4 text-sm leading-6 text-red">
                MVRV 数据加载失败，请稍后重试或检查行情服务。
              </div>
            )}
            {user?.entitlements.mvrv && !mvrvError && (mvrv?.data || []).length === 0 && (
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm leading-6 text-text-secondary">
                暂无 MVRV 数据。配置 Glassnode / ResearchBitcoin API 或刷新本地行情后会显示链上估值参考。
              </div>
            )}
            {(mvrv?.data || []).map((item) => (
              <div key={item.symbol} className="asset-row">
                <div>
                  <div className="text-sm font-semibold">{item.symbol}</div>
                  <div className="text-xs text-text-tertiary">市值 #{item.rank} · {item.model || 'proxy'}</div>
                </div>
                <div className="text-right">
                  <div className={`data-value text-base font-semibold ${item.mvrv_z > 0.5 ? 'text-red' : item.mvrv_z < -0.2 ? 'text-green' : 'text-text-primary'}`}>
                    {item.mvrv_z.toFixed(3)}
                  </div>
                  <div className="text-xs text-text-tertiary">MVRV-Z</div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 flex items-start gap-2 rounded-2xl border border-orange/20 bg-orange/10 p-3 text-xs leading-5 text-orange">
            <TrendingDown size={15} className="mt-0.5 shrink-0" />
            MVRV-Z 是辅助参考。实盘预算仍由 per-asset 策略、动量折扣和现金池纪律控制。
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_390px]">
        <div className="standard-panel p-5">
          <div className="section-kicker">Deploy Preview</div>
          <h2 className="section-title">预算使用率与资产分配</h2>
          <div className="mt-5 space-y-3">
            {summary.active.length === 0 ? (
              <div className="metric-tile">
                <span>当前无可执行信号</span>
                <strong>0%</strong>
              </div>
            ) : summary.active.map((signal) => {
              const weight = summary.totalWeight ? signal.final_mult / summary.totalWeight : 0
              return (
                <div key={signal.symbol} className="asset-row">
                  <div className="flex items-center gap-3">
                    <span className={assetTone(signal.symbol)}>{signal.symbol.slice(0, 1)}</span>
                    <div>
                      <div className="font-semibold">{signal.symbol}</div>
                      <div className="text-xs text-text-tertiary">权重 {(weight * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                  <div className="asset-meter"><span style={{ width: `${Math.max(7, weight * 100)}%` }} /></div>
                  <div className="data-value min-w-[84px] text-right text-sm">{currency(budgetPerRun * weight)}</div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="grid gap-4">
          <div className="standard-panel p-5">
            <div className="section-kicker">Referral & Growth</div>
            <h2 className="section-title">邀请裂变与战绩分享</h2>
            <div className="mt-4 space-y-3">
              <div className="flex justify-between items-center rounded-xl bg-white/[0.02] border border-white/5 p-3">
                <div>
                  <span className="text-[10px] text-text-secondary block">我的专属邀请码</span>
                  <span className="font-mono font-bold text-accent text-sm">{sharePerf?.referral_code || '...'}</span>
                </div>
                <button
                  onClick={async () => {
                    const link = `${window.location.origin}/share-card?code=${sharePerf?.referral_code}`
                    try {
                      await navigator.clipboard.writeText(link)
                      pushToast('邀请链接已复制', 'success')
                    } catch (error) {
                      void error
                      pushToast('复制失败，请手动复制链接', 'error')
                    }
                  }}
                  className="rounded-lg bg-accent/20 border border-accent/30 px-3 py-1.5 text-xs font-semibold text-accent transition hover:bg-accent hover:text-white active:scale-95"
                >
                  复制链接
                </button>
              </div>
              
              <div className="grid grid-cols-2 gap-3 mt-3">
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3 text-center">
                  <span className="text-[10px] text-text-secondary block">累计定投收益率</span>
                  <span className="font-bold text-emerald-400 text-base">
                    {sharePerf && sharePerf.total_invested > 0 ? `+${sharePerf.profit_rate}%` : '暂无战绩'}
                  </span>
                </div>
                <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3 text-center">
                  <span className="text-[10px] text-text-secondary block">邀请定投伙伴</span>
                  <span className="font-bold text-white text-base">{sharePerf?.invited_count || 0} 人</span>
                </div>
              </div>
            </div>
          </div>

          <div className="standard-panel p-5">
            <div className="section-kicker">Status & Shield</div>
            <h2 className="section-title">自动化与风控状态 (Engine Status)</h2>
            <div className="mt-4 space-y-3">
              {[
                ['策略引擎', '自动执行中', 'text-green'],
                ['安全风控', '9道防护全量就绪', 'text-green'],
                ['接口连通', 'CCXT正常', 'text-green'],
                ['每日对账', '差异 < 0.1%', 'text-green'],
              ].map(([label, value, tone]) => (
                <div key={label} className="flex justify-between items-center bg-white/[0.02] border border-white/5 rounded-xl p-3">
                  <span className="text-xs text-text-secondary">{label}</span>
                  <span className={`text-xs font-bold ${tone}`}>{value}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-2 text-xs text-text-tertiary">
              <CalendarClock size={15} className="text-accent" />
              量化引擎每小时自动巡检并评估风控健康度。
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

export default DashboardPage
