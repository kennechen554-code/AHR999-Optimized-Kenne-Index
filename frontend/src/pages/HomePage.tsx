import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, BarChart3, Check, Clock, CreditCard, Database, FileText, Gauge, LockKeyhole, Settings, ShieldAlert, ShieldCheck, TrendingUp, UploadCloud, Workflow, Zap } from 'lucide-react'
import BrandWordmark from '../components/BrandWordmark'
import { fetchBacktestStrategies, fetchPlans } from '../services/api'

interface HomePageProps {
  authed: boolean
}

const SAMPLE_SIGNALS = [
  { symbol: 'BTC', price: '$77,653', ki: '0.4621', zone: '低估', risk: '低', color: 'text-green', width: '72%' },
  { symbol: 'ETH', price: '$2,312', ki: '0.8348', zone: '定投', risk: '中', color: 'text-accent', width: '54%' },
  { symbol: 'SOL', price: '$86.2', ki: '1.1820', zone: '观察', risk: '高', color: 'text-orange', width: '34%' },
]

function HomePage({ authed }: HomePageProps) {
  const { data } = useQuery({
    queryKey: ['plans-public'],
    queryFn: fetchPlans,
    staleTime: 5 * 60_000,
  })
  const { data: strategyResult } = useQuery({
    queryKey: ['backtest-strategies-public'],
    queryFn: fetchBacktestStrategies,
    enabled: authed,
    staleTime: 5 * 60_000,
  })

  const plans = data?.plans || []
  const strategies = strategyResult?.strategies || []

  return (
    <div className="min-h-screen bg-bg text-text-primary">
      <header className="glass-nav fixed left-0 right-0 top-0 z-50 border-b border-white/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center">
            <BrandWordmark caption="Professional Crypto DCA" compact />
          </Link>
          <nav className="hidden items-center gap-5 text-xs text-text-secondary md:flex">
            <Link to="/market" className="text-accent font-semibold hover:text-white">大盘看板</Link>
            <a href="#method" className="hover:text-text-primary">方法论</a>
            <a href="#workflow" className="hover:text-text-primary">工作流</a>
            <a href="#pricing" className="hover:text-text-primary">套餐</a>
            <a href="#risk" className="hover:text-text-primary">风控</a>
            <Link to="/terms" className="hover:text-text-primary">条款</Link>
            <Link to="/privacy" className="hover:text-text-primary">隐私</Link>
          </nav>
          <Link to={authed ? '/app/dashboard' : '/login'} className="primary-button h-10 px-4 text-sm">
            {authed ? '进入工作台' : '登录 / 注册'}
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <section className="hero-scene relative flex min-h-[88vh] items-center overflow-hidden px-4 pt-24 sm:px-6">
        <div className="absolute inset-0 opacity-80">
          <div className="market-grid" />
          <div className="hero-chart-line hero-chart-line-a" />
          <div className="hero-chart-line hero-chart-line-b" />
        </div>
        <div className="relative z-10 mx-auto grid w-full max-w-7xl items-center gap-10 lg:grid-cols-[minmax(0,1fr)_520px]">
          <div className="surface-enter max-w-3xl">
            <h1 className="hero-title text-white">
              Kenne Index
            </h1>
            <p className="mt-5 max-w-2xl text-xl leading-9 text-text-secondary">
              面向加密资产长期配置的专业 DCA 控制台。把估值区间、风险状态、预算纪律和实盘权限收束到一个可订阅、可审计、可执行的工作流。
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={authed ? '/app/dashboard' : '/login'} className="primary-button px-5 py-3">
                开始使用
                <ArrowRight size={16} />
              </Link>
              <Link to="/market" className="secondary-button border-accent/30 text-accent px-5 py-3 hover:bg-accent/10">
                大盘看板
              </Link>
              <a href="#pricing" className="secondary-button px-5 py-3">查看套餐</a>
            </div>
          </div>

          <div className="hero-terminal surface-enter surface-enter-delay">
            <div className="terminal-topbar">
              <div>
                <div className="text-xs text-text-tertiary">Portfolio Signal</div>
                <div className="mt-1 text-lg font-semibold">今日执行建议</div>
              </div>
              <div className="status-pill status-premium">
                <Gauge size={13} />
                风险校准
              </div>
            </div>

            <div className="terminal-gauge">
              <div>
                <div className="text-[11px] text-text-tertiary">综合机会分</div>
                <div className="mt-2 font-mono text-5xl font-semibold">78</div>
              </div>
              <div className="gauge-ring">
                <span>0.82</span>
                <small>AVG KI</small>
              </div>
            </div>

            <div className="mt-5 space-y-2">
              {SAMPLE_SIGNALS.map((item) => (
                <div key={item.symbol} className="asset-row">
                  <div>
                    <div className="text-sm font-semibold">{item.symbol}</div>
                    <div className="text-[11px] text-text-tertiary">Kenne Index {item.ki}</div>
                  </div>
                  <div className="asset-meter"><span style={{ width: item.width }} /></div>
                  <div className="min-w-[82px] text-right">
                    <div className={`text-xs font-semibold ${item.color}`}>{item.zone}</div>
                    <div className="font-mono text-sm">{item.price}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="terminal-footer">
              <span>模拟优先</span>
              <span>Premium 实盘二次确认</span>
              <span>订单审计</span>
            </div>
          </div>
        </div>
      </section>

      <main className="relative z-10 mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <section id="method" className="grid gap-4 md:grid-cols-3">
          {[
            { icon: BarChart3, title: '估值纪律', desc: '幂律模型和几何均线共同约束买入区间，避免只凭情绪加仓。' },
            { icon: TrendingUp, title: '动量过滤', desc: '识别急跌、企稳和正常行情，用不同倍数控制仓位暴露。' },
            { icon: LockKeyhole, title: '执行审计', desc: '模拟与实盘动作分离，Premium 实盘需要权益、确认和日志留痕。' },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="standard-panel surface-enter p-5">
              <Icon className="text-accent" size={22} />
              <h2 className="mt-4 text-base font-semibold">{title}</h2>
              <p className="mt-2 text-sm leading-6 text-text-secondary">{desc}</p>
            </div>
          ))}
        </section>

        <section id="workflow" className="mt-14 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="standard-panel p-6">
            <Workflow size={22} className="text-accent" />
            <div className="mt-4 section-kicker">SaaS Workflow</div>
            <h2 className="section-title">从数据、信号到执行留痕</h2>
            <p className="mt-3 text-sm leading-6 text-text-secondary">
              Kenne Index 将 4H K 线、幂律估值、200 日几何均线、动量过滤和订阅权限串成一条可审计链路。Basic 适合信号验证，Premium 才开放实盘闸门与自定义回测。
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {[
              { icon: Database, title: '数据可信', desc: '本地 CSV、更新时间、链上参考值分层展示。' },
              { icon: BarChart3, title: '策略同源', desc: '前端文案读取后端策略元数据，不复制第二套参数。' },
              { icon: FileText, title: '审计复盘', desc: '模拟与实盘状态分离，支持执行记录导出。' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="standard-panel p-5">
                <Icon size={20} className="text-accent" />
                <h3 className="mt-4 text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-text-secondary">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-14">
          <div className="mb-5">
            <div className="section-kicker">Workspace Modules</div>
            <h2 className="section-title">六个功能区覆盖信号、执行、审计和订阅闭环</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[
              { icon: BarChart3, title: '仪表盘', desc: '查看 Kenne Index、MVRV、风险等级、预算使用率和近期审计摘要。' },
              { icon: Zap, title: '执行', desc: '模拟盘验证、实盘闸门、预算预览和二次确认合并到一个执行中心。' },
              { icon: Clock, title: '审计', desc: '保留 SIM/LIVE 状态、策略备注、订单结果和客户端 CSV 导出。' },
              { icon: Settings, title: '设置', desc: '管理账户、交易所连接、API 权限、策略模式、预算纪律和通知。' },
              { icon: CreditCard, title: '订阅', desc: 'Basic/Premium 权益矩阵与 Stripe Checkout、Customer Portal 对齐。' },
              { icon: UploadCloud, title: '回测', desc: 'Premium 专属，支持上传 CSV 和白名单服务器本地路径两种数据源。' },
            ].map(({ icon: Icon, title, desc }) => (
              <div key={title} className="standard-panel p-5">
                <Icon size={22} className="text-accent" />
                <h3 className="mt-4 text-base font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-text-secondary">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mt-14 standard-panel p-6">
          <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <div className="section-kicker">Per-Asset Strategy</div>
              <h2 className="section-title">双策略计算逻辑</h2>
            </div>
            <div className="text-sm text-text-tertiary">按币种独立周期、预算权重、估值阈值、动量折扣和现金池控制</div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {strategies.length === 0 && (
              <div className="rounded-lg border border-white/10 bg-white/[0.035] p-5 md:col-span-2">
                <div className="text-lg font-semibold">登录后查看后端策略元数据</div>
                <p className="mt-3 text-sm leading-6 text-text-secondary">
                  策略参数由工作台接口返回，公开页只展示方法论摘要，避免未登录请求触发权限错误。
                </p>
              </div>
            )}
            {strategies.map((strategy) => (
              <div key={strategy.mode} className={`rounded-lg border bg-white/[0.035] p-5 ${strategy.default ? 'border-accent/30' : 'border-white/10'}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="text-lg font-semibold">{strategy.label}</div>
                  <span className="status-pill status-basic">{strategy.risk_level}</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-text-secondary">{strategy.description}</p>
                <div className="mt-4 grid gap-2">
                  {strategy.assets.map((asset) => (
                    <div key={asset.symbol} className="metric-tile">
                      <span>{asset.symbol} · {asset.interval_days} 天 · KI {asset.deep_threshold.toFixed(2)} / {asset.dca_threshold.toFixed(2)}</span>
                      <strong>{(asset.budget_weight * 100).toFixed(1)}%</strong>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section id="pricing" className="mt-14">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <div className="section-kicker">Pricing</div>
              <h2 className="section-title">从信号验证到实盘执行</h2>
            </div>
            <div className="hidden text-sm text-text-tertiary sm:block">Stripe 托管订阅 · 可随时管理</div>
          </div>
          <div className="grid items-stretch gap-4 md:grid-cols-2">
            {plans.length === 0 && (
              <div className="standard-panel p-6 md:col-span-2">
                <div className="section-kicker">Pricing Source</div>
                <h3 className="text-base font-semibold">套餐信息正在从后端 Stripe Plans 加载</h3>
                <p className="mt-2 text-sm text-text-secondary">
                  定价页和工作台订阅页共用 /api/v1/stripe/plans，避免前后端套餐文案不一致。
                </p>
              </div>
            )}
            {plans.map((plan) => (
              <div key={plan.id} className={`pricing-card standard-panel p-6 ${plan.recommended ? 'panel-premium' : ''}`}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold">{plan.name} <span className="text-sm text-text-tertiary">{plan.name_en}</span></div>
                    <p className="mt-2 text-sm text-text-secondary">{plan.description}</p>
                  </div>
                  {plan.recommended && <div className="status-pill status-premium">推荐</div>}
                </div>
                <div className="mt-6 flex items-baseline gap-1">
                  <span className="text-4xl font-semibold">{plan.price}</span>
                  <span className="text-sm text-text-tertiary">{plan.period}</span>
                </div>
                <div className="pricing-features mt-6 space-y-2">
                  {plan.features.map((feature) => (
                    <div key={feature} className="flex items-center gap-2 text-sm text-text-secondary">
                      <Check size={15} className="text-green" />
                      {feature}
                    </div>
                  ))}
                </div>
                <Link to={authed ? '/app/billing' : '/login'} className="secondary-button mt-6 w-full justify-center py-3">
                  选择方案
                </Link>
              </div>
            ))}
          </div>
        </section>

        <section id="risk" className="mt-14 standard-panel p-6">
          <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-4">
              <ShieldAlert className="mt-1 text-orange" size={24} />
              <div>
                <h2 className="text-lg font-semibold">风险声明</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-text-secondary">
                  Kenne Index 提供量化信号、预算纪律和执行工具，不承诺收益，也不构成投资建议。加密资产波动剧烈，实盘交易前请确认 API 权限、订单额度和个人风险承受能力。
                </p>
              </div>
            </div>
            <div className="glass-control flex items-center gap-2 px-3 py-2 text-xs text-text-secondary">
              <ShieldCheck size={14} className="text-green" />
              Premium 实盘默认二次确认
            </div>
          </div>
        </section>

        <footer className="mt-10 flex flex-col gap-3 border-t border-white/10 py-6 text-sm text-text-tertiary sm:flex-row sm:items-center sm:justify-between">
          <span>Kenne Index 提供研究和执行辅助工具，不构成投资建议。</span>
          <div className="flex gap-4">
            <Link to="/terms" className="hover:text-text-primary">服务条款</Link>
            <Link to="/privacy" className="hover:text-text-primary">隐私政策</Link>
          </div>
        </footer>

        <section className="mt-14 grid gap-4 lg:grid-cols-2">
          <div className="standard-panel p-6">
            <div className="section-kicker">FAQ</div>
            <h2 className="section-title">常见问题</h2>
            <div className="mt-5 space-y-3">
              {[
                ['Kenne Index 是否直接给投资建议？', '不是。它提供量化信号、预算纪律和审计工具，最终决策仍由用户承担。'],
                ['为什么回测需要 Premium？', '回测会运行完整策略参数、读取本地或上传 CSV，并生成专业绩效指标，属于高级研究能力。'],
                ['服务器本地路径是否安全？', '后端只允许读取 DATA_DIR 和 BACKTEST_ALLOWED_DIRS 白名单内的 CSV，不开放任意路径浏览。'],
              ].map(([question, answer]) => (
                <div key={question} className="rounded-3xl border border-white/10 bg-white/[0.035] p-4">
                  <div className="text-sm font-semibold">{question}</div>
                  <p className="mt-2 text-sm leading-6 text-text-secondary">{answer}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="standard-panel p-6">
            <div className="section-kicker">Governance</div>
            <h2 className="section-title">专业金融 SaaS 必备边界</h2>
            <div className="mt-5 grid gap-3">
              {[
                ['数据可信度', '展示数据来源、更新时间、代理指标说明和模型版本。'],
                ['权限控制', '套餐权益只做前端展示，实盘与回测由后端强制校验。'],
                ['执行确认', 'Premium 实盘仍需每次二次确认，不允许静默下单。'],
                ['审计留痕', '执行结果、策略模式、订单状态和异常原因可复盘。'],
              ].map(([label, value]) => (
                <div key={label} className="metric-tile">
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default HomePage
