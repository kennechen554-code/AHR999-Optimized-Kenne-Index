import { useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Activity, ArrowRight, Coins, LineChart, Shield, Sparkles } from 'lucide-react'
import { fetchPublicSignals } from '../services/api'
import type { PublicSignal } from '../types/api'

interface ChartPoint {
  date: string
  index: number
  price: number
}

interface SvgPoint {
  x: number
  y: number
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function currency(value: unknown): string {
  const amount = asFiniteNumber(value)
  if (amount === null) return '-'
  return amount.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: amount > 1000 ? 0 : 2,
  })
}

function numberText(value: unknown, digits = 2): string {
  const numberValue = asFiniteNumber(value)
  return numberValue === null ? '-' : numberValue.toFixed(digits)
}

function assetGradient(symbol: string): string {
  if (symbol === 'BTC') return 'from-amber-500 to-orange-600'
  if (symbol === 'ETH') return 'from-indigo-500 to-purple-600'
  return 'from-cyan-500 to-emerald-600'
}

function zoneClass(zone: string): string {
  if (zone === '极低估') return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
  if (zone === '定投区') return 'border-cyan-500/30 bg-cyan-500/15 text-cyan-300'
  return 'border-rose-500/30 bg-rose-500/15 text-rose-300'
}

function getRange(values: number[]): { min: number; max: number } {
  if (values.length === 0) return { min: 0, max: 1 }
  const min = Math.min(...values)
  const max = Math.max(...values)
  if (min === max) return { min: min - 1, max: max + 1 }
  const padding = (max - min) * 0.16
  return { min: min - padding, max: max + padding }
}

function toSvgPoints(data: ChartPoint[], read: (point: ChartPoint) => number, range: { min: number; max: number }): SvgPoint[] {
  const left = 36
  const top = 20
  const width = 720
  const height = 250
  const usableWidth = width - left - 28
  const usableHeight = height - top - 28
  return data.map((point, index) => ({
    x: left + (data.length <= 1 ? 0 : (index / (data.length - 1)) * usableWidth),
    y: top + (1 - (read(point) - range.min) / (range.max - range.min)) * usableHeight,
  }))
}

function pathFrom(points: SvgPoint[]): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ')
}

export default function MarketPage() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTC')
  const { data: signals, isLoading, error } = useQuery<PublicSignal[]>({
    queryKey: ['publicSignals'],
    queryFn: () => fetchPublicSignals({ suppressToast: true }),
    refetchInterval: 180000,
  })

  const activeSignal = useMemo(
    () => signals?.find((signal) => signal.symbol === selectedSymbol),
    [signals, selectedSymbol],
  )

  const chartData = useMemo<ChartPoint[]>(() => {
    if (!activeSignal?.history) return []
    return activeSignal.history
      .map((point) => ({
        date: point.date.slice(5),
        index: point.kenne_index,
        price: point.price,
      }))
      .filter((point) => Number.isFinite(point.index) && Number.isFinite(point.price))
  }, [activeSignal])

  const chart = useMemo(() => {
    const indexPoints = toSvgPoints(chartData, (point) => point.index, getRange(chartData.map((point) => point.index)))
    const pricePoints = toSvgPoints(chartData, (point) => point.price, getRange(chartData.map((point) => point.price)))
    return {
      indexPath: pathFrom(indexPoints),
      pricePath: pathFrom(pricePoints),
      areaPath: indexPoints.length
        ? `${pathFrom(indexPoints)} L ${indexPoints[indexPoints.length - 1].x.toFixed(1)} 250 L ${indexPoints[0].x.toFixed(1)} 250 Z`
        : '',
      labels: chartData.filter((_, index) => index === 0 || index === chartData.length - 1),
    }
  }, [chartData])

  return (
    <div className="min-h-screen bg-bg text-text-primary selection:bg-accent/30 selection:text-white">
      <header className="sticky top-0 z-50 border-b border-white/5 bg-bg/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-tr from-accent to-indigo-600 text-xl font-black text-white shadow-lg shadow-accent/20">
              K
            </span>
            <span className="bg-gradient-to-r from-white to-text-secondary bg-clip-text text-xl font-bold text-transparent">
              Kenne Index
            </span>
            <span className="hidden rounded-full bg-white/5 px-2.5 py-0.5 text-xs font-medium text-accent sm:inline-block">
              实时看板
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/login" className="text-sm font-medium text-text-secondary transition-colors hover:text-white">
              登录
            </Link>
            <Link
              to="/login?action=register"
              className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-accent to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-accent/20 transition-all hover:scale-102"
            >
              免费加入
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <section className="mb-16 text-center">
          <div className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-white/5 bg-white/5 px-3 py-1 text-xs font-semibold text-accent">
            <Sparkles className="h-3.5 w-3.5" />
            基于智能数学幂律拟合与动量控制的避险算法
          </div>
          <h1 className="bg-gradient-to-b from-white to-neutral-400 bg-clip-text text-4xl font-extrabold text-transparent sm:text-6xl">
            Kenne Index 市场温度计
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-text-secondary sm:text-lg">
            每日动态校准数据，以透明的智能公式和可回测收益，帮助长期配置者减少情绪化决策。
          </p>
        </section>

        {isLoading ? (
          <div className="flex min-h-[40vh] items-center justify-center">
            <span className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : error ? (
          <div className="glass-panel border-red/20 bg-red/5 p-6 text-center">
            <p className="font-semibold text-red">无法加载市场信号，请稍后刷新重试。</p>
          </div>
        ) : (
          <div className="space-y-10">
            <div className="flex flex-wrap justify-center gap-2.5 border-b border-white/5 pb-5 sm:justify-start">
              {signals?.map((signal) => (
                <button
                  key={signal.symbol}
                  type="button"
                  onClick={() => setSelectedSymbol(signal.symbol)}
                  className={`flex items-center gap-2.5 rounded-lg border px-5 py-3 text-sm font-semibold transition-all ${
                    selectedSymbol === signal.symbol
                      ? 'scale-102 border-white/20 bg-white/5 text-white shadow-xl'
                      : 'border-white/5 bg-transparent text-text-secondary hover:border-white/10 hover:text-white'
                  }`}
                >
                  <span className={`h-2.5 w-2.5 rounded-full bg-gradient-to-r ${assetGradient(signal.symbol)}`} />
                  {signal.symbol}
                  <span className={`rounded-md border px-2 py-0.5 text-xs ${zoneClass(signal.zone)}`}>{signal.zone}</span>
                </button>
              ))}
            </div>

            {activeSignal && (
              <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
                <section className="glass-panel flex flex-col justify-between border-white/5 p-6">
                  <div>
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <span className={`flex h-11 w-11 items-center justify-center rounded-lg bg-gradient-to-tr ${assetGradient(activeSignal.symbol)} text-lg font-bold text-white`}>
                          {activeSignal.symbol}
                        </span>
                        <div>
                          <h2 className="text-2xl font-extrabold tracking-tight">{activeSignal.symbol} 指标</h2>
                          <p className="text-xs text-text-secondary">数据刷新于: {activeSignal.date || '-'}</p>
                        </div>
                      </div>
                      <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${zoneClass(activeSignal.zone)}`}>
                        {activeSignal.zone}
                      </span>
                    </div>

                    <div className="mt-8 space-y-5">
                      <div>
                        <span className="text-xs font-medium text-text-secondary">当前价格</span>
                        <div className="text-3xl font-black tracking-tight">{currency(activeSignal.price)}</div>
                      </div>
                      <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-4">
                        <Metric label="Kenne Index" value={numberText(activeSignal.kenne_index, 4)} accent="text-accent" />
                        <Metric label="定投评分" value={`${numberText(activeSignal.score, 0)} / 100`} accent="text-indigo-400" />
                        <Metric label="200日均线" value={currency(activeSignal.cost_200)} />
                        <Metric label="幂律估值" value={currency(activeSignal.valuation)} />
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 space-y-2 border-t border-white/5 pt-5">
                    <div className="flex justify-between text-xs">
                      <span className="text-text-secondary">执行比率倍数</span>
                      <span className="font-semibold text-white">
                        {numberText(activeSignal.final_mult, 2)}x ({activeSignal.momentum === 'FALLING' ? '避险打折' : '常规定投'})
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-white/5">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-accent to-indigo-600"
                        style={{ width: `${Math.min(100, (asFiniteNumber(activeSignal.final_mult) ?? 0) * 50)}%` }}
                      />
                    </div>
                  </div>
                </section>

                <section className="glass-panel min-w-0 border-white/5 p-6 lg:col-span-2">
                  <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <LineChart className="h-5 w-5 text-accent" />
                      <h3 className="text-lg font-bold text-white">180 日历史走势</h3>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-text-secondary">
                      <Legend color="bg-accent" label="Kenne Index" />
                      <Legend color="bg-indigo-500" label="收盘价格" />
                    </div>
                  </div>

                  <div className="h-[300px] min-h-[300px] w-full min-w-0">
                    {chartData.length ? (
                      <svg className="h-full w-full" viewBox="0 0 720 300" role="img" aria-label={`${activeSignal.symbol} 180 日走势`}>
                        <defs>
                          <linearGradient id="market-index-fill" x1="0" x2="0" y1="0" y2="1">
                            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.24" />
                            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
                          </linearGradient>
                        </defs>
                        {[60, 115, 170, 225].map((y) => (
                          <line key={y} x1="36" x2="692" y1={y} y2={y} stroke="rgba(255,255,255,0.06)" />
                        ))}
                        <path d={chart.areaPath} fill="url(#market-index-fill)" />
                        <path d={chart.indexPath} fill="none" stroke="var(--color-accent)" strokeLinecap="round" strokeWidth="3" />
                        <path d={chart.pricePath} fill="none" stroke="#6366f1" strokeDasharray="8 7" strokeLinecap="round" strokeWidth="2.2" />
                        {chart.labels.map((label, index) => (
                          <text key={label.date} x={index === 0 ? 36 : 660} y="282" fill="rgba(196,199,200,0.62)" fontSize="12">
                            {label.date}
                          </text>
                        ))}
                      </svg>
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-text-secondary">无历史图表数据</div>
                    )}
                  </div>
                </section>
              </div>
            )}
          </div>
        )}

        <section className="mt-20">
          <div className="rounded-lg border border-white/5 bg-gradient-to-b from-white/[0.03] to-transparent p-8 text-center sm:p-12">
            <div className="mx-auto max-w-2xl space-y-6">
              <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">想彻底解放双手？</h2>
              <p className="text-base leading-relaxed text-text-secondary">
                注册 Kenne Index 会员，绑定交易所 API 权限，系统将自动读取行情信号、执行定投防踩空策略，并发送每日智能 AI 日报与告警。
              </p>
              <div className="mx-auto grid max-w-md grid-cols-1 gap-4 pt-4 sm:grid-cols-3">
                <Feature icon={<Shield className="h-6 w-6 text-accent" />} title="资金自托管" caption="API 无提现权限" />
                <Feature icon={<Activity className="h-6 w-6 text-indigo-400" />} title="全自动化" caption="24h 智能云执行" />
                <Feature icon={<Coins className="h-6 w-6 text-emerald-400" />} title="双重风控" caption="月预算与熔断" />
              </div>
              <Link
                to="/login?action=register"
                className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-accent to-indigo-600 px-8 py-4 text-base font-bold text-white shadow-xl shadow-accent/25 transition-all hover:scale-102"
              >
                免费开通智能定投账户
                <ArrowRight className="h-5 w-5" />
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="mx-auto mt-20 max-w-7xl space-y-3 border-t border-white/5 px-4 py-16 text-center text-xs text-text-secondary sm:px-6">
        <p className="mx-auto max-w-3xl leading-relaxed">
          风险披露声明：加密货币投资具有极高的市场和资产风险。Kenne Index 模型的所有回测数据及信号仅作为技术性参考，不构成任何形式的投资建议或金融财务意见。
        </p>
        <p>© 2026 Kenne Index SaaS Inc. 保留所有权利。</p>
      </footer>
    </div>
  )
}

function Metric({ label, value, accent = 'text-white' }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <span className="block text-xs text-text-secondary">{label}</span>
      <span className={`text-sm font-semibold tracking-tight ${accent}`}>{value}</span>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  )
}

function Feature({ icon, title, caption }: { icon: ReactNode; title: string; caption: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-white/5 bg-white/[0.02] p-4">
      {icon}
      <span className="text-sm font-semibold text-white">{title}</span>
      <span className="text-xs text-text-secondary">{caption}</span>
    </div>
  )
}
