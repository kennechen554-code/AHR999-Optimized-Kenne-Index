import { Link } from 'react-router-dom'
import { CheckCircle2, Circle, CreditCard, KeyRound, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import type { UserConfig, UserInfo } from '../types/api'

interface OnboardingChecklistProps {
  user: UserInfo | null
  config?: UserConfig
}

export function buildOnboardingSteps(user: UserInfo | null, config?: UserConfig) {
  return [
    {
      id: 'exchange',
      title: '连接交易所并保持最小权限',
      desc: '填写 API Key 后，只启用现货交易权限，禁用提现，并尽量绑定 IP 白名单。',
      done: Boolean(config?.api_key && config.api_key !== ''),
      to: '/app/settings',
      icon: KeyRound,
    },
    {
      id: 'simulated',
      title: '先使用模拟盘验证策略',
      desc: '默认保持模拟盘优先，确认预算、信号和审计结果后再考虑实盘。',
      done: Boolean(config?.simulated),
      to: '/app/execute',
      icon: ShieldCheck,
    },
    {
      id: 'budget',
      title: '设置预算纪律',
      desc: '确认月度预算、执行间隔和策略模式，避免单次投入超出承受范围。',
      done: Boolean(config?.budget_amount && config.budget_amount > 0 && config.run_interval_days > 0),
      to: '/app/settings',
      icon: SlidersHorizontal,
    },
    {
      id: 'billing',
      title: '了解订阅与实盘闸门',
      desc: 'Basic 适合信号验证，Premium 才开放实盘、自动化和回测等高级能力。',
      done: Boolean(user?.entitlements.live_trading),
      to: '/app/billing',
      icon: CreditCard,
    },
  ]
}

export default function OnboardingChecklist({ user, config }: OnboardingChecklistProps) {
  const steps = buildOnboardingSteps(user, config)
  const completed = steps.filter((step) => step.done).length

  return (
    <section className="standard-panel p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="section-kicker">Onboarding</div>
          <h2 className="section-title">上线前检查清单</h2>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            用四步把账户、交易所、预算和订阅边界配置完整。完成前建议只运行模拟盘。
          </p>
        </div>
        <span className="status-pill status-basic">{completed}/{steps.length} 完成</span>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {steps.map(({ id, title, desc, done, to, icon: Icon }) => (
          <Link key={id} to={to} className="rounded-3xl border border-white/10 bg-white/[0.035] p-4 transition hover:border-white/25 hover:bg-white/[0.06]">
            <div className="flex items-start gap-3">
              <div className={`mt-0.5 ${done ? 'text-green' : 'text-text-tertiary'}`}>
                {done ? <CheckCircle2 size={18} /> : <Circle size={18} />}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Icon size={15} className="text-accent" />
                  {title}
                </div>
                <p className="mt-2 text-xs leading-5 text-text-secondary">{desc}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  )
}
