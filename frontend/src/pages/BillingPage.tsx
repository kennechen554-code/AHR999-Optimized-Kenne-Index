import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, CreditCard, ExternalLink, LockKeyhole, ShieldCheck, Sparkles } from 'lucide-react'
import { createBillingPortal, createCheckout, devUpgradePlan, fetchMe, fetchPlans } from '../services/api'

function BillingPage() {
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const { data: user, refetch: refetchMe } = useQuery({ queryKey: ['me'], queryFn: fetchMe })
  const { data: plansResult, isLoading: plansLoading, isError: plansError } = useQuery({ queryKey: ['plans'], queryFn: fetchPlans })

  const currentPlan = user?.plan || 'free'
  const plans = plansResult?.plans || []
  const premiumUnlocked = Boolean(user?.entitlements.live_trading)

  const statusText = useMemo(() => {
    if (!user) return '加载中'
    if (currentPlan === 'free') return '未订阅'
    if (user.subscription_status === 'active') return '订阅有效'
    if (user.subscription_status === 'trialing') return '试用中'
    if (user.subscription_status === 'past_due') return '付款异常'
    return user.subscription_status || '未知状态'
  }, [currentPlan, user])

  const startCheckout = async (plan: string) => {
    setBusy(plan)
    setMessage('')
    try {
      const result = await createCheckout(plan)
      window.location.href = result.checkout_url
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '创建支付会话失败')
    } finally {
      setBusy('')
    }
  }

  const openPortal = async () => {
    setBusy('portal')
    setMessage('')
    try {
      const result = await createBillingPortal()
      window.location.href = result.portal_url
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '创建订阅管理入口失败')
    } finally {
      setBusy('')
      refetchMe()
    }
  }

  return (
    <div className="space-y-5">
      {import.meta.env.DEV && (
        <section className="standard-panel border-orange/20 bg-orange/5 p-5 relative overflow-hidden">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-orange">
                <Sparkles size={16} />
                <span className="text-xs font-semibold uppercase tracking-wider">开发演示工具 (仅本地开发可见)</span>
              </div>
              <h3 className="mt-1 text-sm font-semibold text-text-primary">变现测试控制台</h3>
              <p className="mt-1 text-xs text-text-secondary leading-5">
                无需对接 Stripe Webhook，一键模拟租户套餐变更以测试前台功能锁的解锁和展示效果。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={async () => {
                  setBusy('dev_basic')
                  setMessage('')
                  try {
                    await devUpgradePlan('basic')
                    refetchMe()
                  } catch (err) {
                    setMessage(err instanceof Error ? err.message : '模拟失败')
                  } finally {
                    setBusy('')
                  }
                }}
                disabled={busy !== ''}
                className="secondary-button px-3 py-2 text-xs border-orange/20 hover:border-orange/40 text-orange"
              >
                模拟订阅 Basic
              </button>
              <button
                onClick={async () => {
                  setBusy('dev_premium')
                  setMessage('')
                  try {
                    await devUpgradePlan('premium')
                    refetchMe()
                  } catch (err) {
                    setMessage(err instanceof Error ? err.message : '模拟失败')
                  } finally {
                    setBusy('')
                  }
                }}
                disabled={busy !== ''}
                className="primary-button px-3 py-2 text-xs bg-orange/20 border-orange/30 text-white hover:bg-orange/30"
              >
                模拟订阅 Premium
              </button>
              <button
                onClick={async () => {
                  setBusy('dev_free')
                  setMessage('')
                  try {
                    await devUpgradePlan('free')
                    refetchMe()
                  } catch (err) {
                    setMessage(err instanceof Error ? err.message : '模拟失败')
                  } finally {
                    setBusy('')
                  }
                }}
                disabled={busy !== ''}
                className="danger-button px-3 py-2 text-xs"
              >
                重置为 Free
              </button>
            </div>
          </div>
        </section>
      )}

      <section className="standard-panel surface-enter p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="section-kicker">Billing</div>
            <h2 className="section-title">订阅与实盘权限</h2>
            <p className="mt-2 max-w-2xl text-sm text-text-secondary">
              Stripe 负责支付和订阅管理。前端仅展示权益，实盘交易仍由后端按照套餐和二次确认强制校验。
            </p>
          </div>
          <div className="glass-control px-4 py-3">
            <div className="text-[11px] text-text-tertiary">当前套餐</div>
            <div className="mt-1 flex items-center gap-2">
              <CreditCard size={16} className="text-accent" />
              <span className="text-lg font-semibold capitalize">{currentPlan}</span>
              <span className={`status-pill ${premiumUnlocked ? 'status-premium' : 'status-basic'}`}>{statusText}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="grid items-stretch gap-4 lg:grid-cols-2">
        {plansLoading && (
          <div className="standard-panel p-6 lg:col-span-2">
            <div className="section-kicker">Plans</div>
            <h3 className="text-base font-semibold">正在加载套餐信息</h3>
            <p className="mt-2 text-sm text-text-secondary">套餐来自后端 Stripe Plans，与后端权益校验保持一致。</p>
          </div>
        )}
        {plansError && (
          <div className="standard-panel border-red/30 p-6 text-red lg:col-span-2">
            套餐加载失败，请稍后重试或检查 Stripe 配置。
          </div>
        )}
        {!plansLoading && !plansError && plans.length === 0 && (
          <div className="standard-panel p-6 lg:col-span-2">
            <div className="section-kicker">Plans</div>
            <h3 className="text-base font-semibold">暂无可订阅套餐</h3>
            <p className="mt-2 text-sm text-text-secondary">请确认后端 Stripe price ID 已配置，并检查 `/api/v1/stripe/plans`。</p>
          </div>
        )}
        {plans.map((plan) => {
          const active = currentPlan === plan.id
          return (
            <div key={plan.id} className={`pricing-card standard-panel p-6 ${plan.recommended ? 'panel-premium' : ''}`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold">{plan.name}</h3>
                    {plan.recommended && <Sparkles size={16} className="text-orange" />}
                  </div>
                  <p className="mt-2 text-sm text-text-secondary">{plan.description}</p>
                </div>
                {active && <span className="status-pill status-premium">当前</span>}
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

              <button
                onClick={() => startCheckout(plan.id)}
                disabled={busy === plan.id || active}
                className="primary-button mt-6 w-full justify-center py-3 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {active ? '已启用' : busy === plan.id ? '正在创建支付会话' : `订阅${plan.name}`}
              </button>
            </div>
          )
        })}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center gap-2">
            <ShieldCheck size={18} className="text-green" />
            <h3 className="text-base font-semibold">Premium 实盘解锁条件</h3>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {[
              ['套餐状态', premiumUnlocked ? '已解锁' : '未解锁'],
              ['二次确认', '每次实盘执行必须确认'],
              ['自定义回测', user?.entitlements.backtesting ? '已解锁' : 'Premium 专属'],
              ['默认模式', '模拟盘优先'],
              ['订单审计', '执行结果写入历史记录'],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                <div className="text-[11px] text-text-tertiary">{label}</div>
                <div className="mt-1 text-sm font-medium">{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="standard-panel p-5">
          <LockKeyhole size={20} className="text-accent" />
          <h3 className="mt-3 text-base font-semibold">管理订阅</h3>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            在 Stripe Customer Portal 中更新付款方式、查看发票或取消订阅。
          </p>
          <button onClick={openPortal} disabled={busy === 'portal'} className="secondary-button mt-5 w-full justify-center py-3">
            {busy === 'portal' ? '正在打开' : '打开订阅管理'}
            <ExternalLink size={15} />
          </button>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="section-kicker">Financial SaaS Readiness</div>
        <h3 className="text-base font-semibold">专业金融软件能力矩阵</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          {[
            ['数据可信度', '更新时间与来源展示'],
            ['模型治理', '策略版本与参数摘要'],
            ['权限边界', '后端强制套餐校验'],
            ['风险留痕', '实盘确认与审计记录'],
          ].map(([label, value]) => (
            <div key={label} className="metric-tile">
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>

      {message && (
        <div className="rounded-lg border border-orange/30 bg-orange/10 px-4 py-3 text-sm text-orange">
          {message}
        </div>
      )}
    </div>
  )
}

export default BillingPage
