import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  TrendingUp,
  Activity,
  ArrowRight,
  Shield,
  Coins,
  LineChart as LineIcon,
  Sparkles,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { fetchPublicSignals } from '../services/api'
import type { PublicSignal } from '../types/api'

// 美化货币格式
function currency(value: number) {
  return value.toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value > 1000 ? 0 : 2,
  })
}

// 币种主色调样式
function getAssetColor(symbol: string) {
  if (symbol === 'BTC') return 'from-amber-500 to-orange-600'
  if (symbol === 'ETH') return 'from-indigo-500 to-purple-600'
  return 'from-cyan-500 to-emerald-600'
}

// 估值状态色调
function getZoneBadgeClass(zone: string) {
  if (zone === '极低估') return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
  if (zone === '定投区') return 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
  return 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
}

export default function MarketPage() {
  const [selectedSymbol, setSelectedSymbol] = useState('BTC')

  // 发起匿名数据拉取
  const { data: signals, isLoading, error } = useQuery<PublicSignal[]>({
    queryKey: ['publicSignals'],
    queryFn: fetchPublicSignals,
    refetchInterval: 180000, // 每3分钟自动刷新
  })

  // 找当前选择的币种数据
  const activeSignal = useMemo(() => {
    return signals?.find((s) => s.symbol === selectedSymbol)
  }, [signals, selectedSymbol])

  // 走势图数据转换
  const chartData = useMemo(() => {
    if (!activeSignal || !activeSignal.history) return []
    return activeSignal.history.map((pt) => ({
      date: pt.date.slice(5), // 简化为 MM-DD
      'Kenne Index': pt.kenne_index,
      价格: pt.price,
      估值下沿: pt.valuation,
    }))
  }, [activeSignal])

  return (
    <div className="min-h-screen bg-bg text-text-primary selection:bg-accent/30 selection:text-white">
      {/* 炫酷背景光圈 */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-accent/10 blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-500/10 blur-[150px] pointer-events-none" />

      {/* 头部导航栏 */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-bg/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-accent to-indigo-600 text-white font-black text-xl shadow-lg shadow-accent/20">
              K
            </span>
            <span className="bg-gradient-to-r from-white to-text-secondary bg-clip-text text-xl font-bold tracking-tight text-transparent">
              Kenne Index
            </span>
            <span className="hidden sm:inline-block rounded-full bg-white/5 px-2.5 py-0.5 text-xs font-medium text-accent">
              实时看板
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              to="/login"
              className="text-sm font-medium text-text-secondary hover:text-white transition-colors"
            >
              登录
            </Link>
            <Link
              to="/login?action=register"
              className="group flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-accent to-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-accent/20 transition-all hover:scale-102 hover:shadow-accent/30 active:scale-98"
            >
              免费加入
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* 主要内容区域 */}
      <main className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        {/* 广告标语与主视觉 */}
        <div className="text-center mb-16">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-white/5 bg-white/5 px-3 py-1 text-xs font-semibold text-accent backdrop-blur-sm mb-4">
            <Sparkles className="h-3.5 w-3.5" />
            基于智能数学幂律拟合与动量控制的避险算法
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight sm:text-6xl bg-gradient-to-b from-white to-neutral-400 bg-clip-text text-transparent">
            Kenne Index 市场温度计
          </h1>
          <p className="mt-4 mx-auto max-w-2xl text-base sm:text-lg text-text-secondary">
            告别情绪追高杀跌。每日动态校准数据，以透明的智能公式和可回测收益，实现加密货币的高效定投。
          </p>
        </div>

        {/* 核心看板卡片 */}
        {isLoading ? (
          <div className="flex min-h-[40vh] items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <span className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
              <p className="text-sm text-text-secondary">正在拟合幂律模型并加载最新信号...</p>
            </div>
          </div>
        ) : error ? (
          <div className="glass-panel border-red/20 bg-red/5 p-6 text-center">
            <p className="text-red font-semibold">无法加载市场信号，请稍后刷新重试。</p>
          </div>
        ) : (
          <div className="space-y-10">
            {/* 币种快捷标签切换 */}
            <div className="flex flex-wrap gap-2.5 justify-center sm:justify-start border-b border-white/5 pb-5">
              {signals?.map((s) => (
                <button
                  key={s.symbol}
                  onClick={() => setSelectedSymbol(s.symbol)}
                  className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl border text-sm font-semibold transition-all duration-300 ${
                    selectedSymbol === s.symbol
                      ? 'bg-white/5 border-white/20 text-white shadow-xl scale-102'
                      : 'border-white/5 bg-transparent text-text-secondary hover:border-white/10 hover:text-white'
                  }`}
                >
                  <span className={`h-2.5 w-2.5 rounded-full bg-gradient-to-r ${getAssetColor(s.symbol)}`} />
                  {s.symbol}
                  <span className={`text-xs px-2 py-0.5 rounded-md ${getZoneBadgeClass(s.zone)}`}>
                    {s.zone}
                  </span>
                </button>
              ))}
            </div>

            {/* 大图看板与数值分析 */}
            {activeSignal && (
              <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
                {/* 核心指标展示面板 */}
                <div className="glass-panel p-6 flex flex-col justify-between border-white/5 relative overflow-hidden group">
                  <div className="absolute top-0 right-0 h-32 w-32 bg-accent/5 rounded-bl-[100px] -z-10 group-hover:bg-accent/10 transition-colors duration-500" />
                  
                  <div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-tr ${getAssetColor(activeSignal.symbol)} text-white font-bold text-lg shadow-md`}>
                          {activeSignal.symbol}
                        </span>
                        <div>
                          <h2 className="font-extrabold text-2xl tracking-tight">{activeSignal.symbol} 指标</h2>
                          <p className="text-xs text-text-secondary">数据刷新于: {activeSignal.date}</p>
                        </div>
                      </div>
                      <span className={`text-xs font-semibold px-3 py-1 rounded-full ${getZoneBadgeClass(activeSignal.zone)}`}>
                        {activeSignal.zone}
                      </span>
                    </div>

                    <div className="mt-8 space-y-5">
                      <div>
                        <span className="text-xs text-text-secondary font-medium">当前价格</span>
                        <div className="text-3xl font-black tracking-tight">{currency(activeSignal.price)}</div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-4">
                        <div>
                          <span className="text-xs text-text-secondary block">Kenne Index 指数</span>
                          <span className="text-xl font-bold tracking-tight text-accent">{activeSignal.kenne_index}</span>
                        </div>
                        <div>
                          <span className="text-xs text-text-secondary block">综合定投评分</span>
                          <span className="text-xl font-bold tracking-tight text-indigo-400">{activeSignal.score} / 100</span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-4">
                        <div>
                          <span className="text-xs text-text-secondary block">200日几何均线</span>
                          <span className="text-sm font-semibold">{currency(activeSignal.cost_200)}</span>
                        </div>
                        <div>
                          <span className="text-xs text-text-secondary block">幂律增长估值</span>
                          <span className="text-sm font-semibold">{currency(activeSignal.valuation)}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 border-t border-white/5 pt-5 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-text-secondary">执行比率倍数</span>
                      <span className="font-semibold text-white">
                        {activeSignal.final_mult}x ({activeSignal.momentum === 'FALLING' ? '避险打折' : '常规定投'})
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-white/5 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-accent to-indigo-600 transition-all duration-500"
                        style={{ width: `${Math.min(100, activeSignal.final_mult * 50)}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* 走势图表画板 */}
                <div className="glass-panel p-6 lg:col-span-2 border-white/5 flex flex-col justify-between">
                  <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
                    <div className="flex items-center gap-2">
                      <LineIcon className="h-5 w-5 text-accent" />
                      <h3 className="font-bold text-lg text-white">180 日历史走势大盘</h3>
                    </div>
                    <div className="text-xs text-text-secondary flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-accent" /> Kenne Index
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="h-2 w-2 rounded-full bg-indigo-500" /> 收盘价格
                      </span>
                    </div>
                  </div>

                  <div className="h-[300px] w-full">
                    {chartData.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData}>
                          <defs>
                            <linearGradient id="colorIndex" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="var(--color-accent, #cf5dff)" stopOpacity={0.2} />
                              <stop offset="95%" stopColor="var(--color-accent, #cf5dff)" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="rgba(255,255,255,0.03)" vertical={false} />
                          <XAxis
                            dataKey="date"
                            tickLine={false}
                            axisLine={false}
                            tick={{ fill: '#8A8F98', fontSize: 10 }}
                            dy={10}
                          />
                          <YAxis
                            yAxisId="left"
                            orientation="left"
                            tickLine={false}
                            axisLine={false}
                            tick={{ fill: '#8A8F98', fontSize: 10 }}
                            dx={-10}
                          />
                          <YAxis
                            yAxisId="right"
                            orientation="right"
                            tickLine={false}
                            axisLine={false}
                            tick={{ fill: '#8A8F98', fontSize: 10 }}
                            dx={10}
                          />
                          <Tooltip
                            contentStyle={{
                              backgroundColor: 'rgba(16, 17, 21, 0.95)',
                              borderColor: 'rgba(255,255,255,0.08)',
                              borderRadius: '12px',
                              boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                            }}
                            labelStyle={{ color: '#8A8F98', fontWeight: 'bold' }}
                            itemStyle={{ color: '#fff' }}
                          />
                          <Area
                            yAxisId="left"
                            type="monotone"
                            dataKey="Kenne Index"
                            stroke="var(--color-accent, #cf5dff)"
                            strokeWidth={2}
                            fillOpacity={1}
                            fill="url(#colorIndex)"
                          />
                          <Area
                            yAxisId="right"
                            type="monotone"
                            dataKey="价格"
                            stroke="#5e6fff"
                            strokeWidth={1.5}
                            fill="none"
                            strokeDasharray="4 4"
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex h-full items-center justify-center text-sm text-text-secondary">
                        无历史图表数据
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 裂变增长引导注册 CTA 面板 */}
        <section className="mt-20">
          <div className="relative rounded-3xl overflow-hidden border border-white/5 bg-gradient-to-b from-white/[0.03] to-transparent p-8 sm:p-12 text-center backdrop-blur-sm">
            {/* 卡片背光 */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[300px] w-[300px] rounded-full bg-accent/15 blur-[80px] pointer-events-none" />

            <div className="relative max-w-2xl mx-auto space-y-6">
              <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl text-white">
                想彻底解放双手？
              </h2>
              <p className="text-base text-text-secondary leading-relaxed">
                注册 Kenne Index 会员，绑定交易所 API 权限，系统将全自动读取行情信号、执行定投防踩空策略、并发送每日智能 AI 日报与告警。
              </p>

              <div className="mx-auto grid max-w-md grid-cols-1 gap-4 sm:grid-cols-3 pt-4">
                <div className="flex flex-col items-center gap-2 p-4 rounded-2xl bg-white/[0.02] border border-white/5">
                  <Shield className="h-6 w-6 text-accent" />
                  <span className="text-sm font-semibold text-white">资金自托管</span>
                  <span className="text-xs text-text-secondary">API 无提现权限</span>
                </div>
                <div className="flex flex-col items-center gap-2 p-4 rounded-2xl bg-white/[0.02] border border-white/5">
                  <Activity className="h-6 w-6 text-indigo-400" />
                  <span className="text-sm font-semibold text-white">全自动化</span>
                  <span className="text-xs text-text-secondary">24h 智能云执行</span>
                </div>
                <div className="flex flex-col items-center gap-2 p-4 rounded-2xl bg-white/[0.02] border border-white/5">
                  <Coins className="h-6 w-6 text-emerald-400" />
                  <span className="text-sm font-semibold text-white">双重风控</span>
                  <span className="text-xs text-text-secondary">月预算与熔断</span>
                </div>
              </div>

              <div className="pt-8">
                <Link
                  to="/login?action=register"
                  className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-accent to-indigo-600 px-8 py-4 text-base font-bold text-white shadow-xl shadow-accent/25 hover:scale-102 hover:shadow-accent/35 active:scale-98 transition-all"
                >
                  免费开通智能定投账户
                  <ArrowRight className="h-5 w-5" />
                </Link>
                <div className="mt-3 text-xs text-text-secondary">
                  注册即送 7 天 Premium 试用卡 · 随时取消订阅
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* 公开免责底栏 */}
      <footer className="mx-auto max-w-7xl px-4 py-16 sm:px-6 border-t border-white/5 mt-20 text-center text-xs text-text-secondary space-y-3">
        <p className="max-w-3xl mx-auto leading-relaxed">
          风险披露声明：加密货币投资具有极高的市场和资产风险。Kenne Index 模型的所有回测数据及信号仅作为技术性参考，不构成任何形式的投资建议或金融财务意见。请根据自身的风险承受力谨慎定投。
        </p>
        <p>© 2026 Kenne Index SaaS Inc. 保留所有权利。</p>
      </footer>
    </div>
  )
}
