import { Link, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ShieldCheck } from 'lucide-react'
import OnboardingChecklist from '../components/OnboardingChecklist'
import { fetchConfig } from '../services/api'
import type { UserInfo } from '../types/api'

export default function OnboardingPage() {
  const { user } = useOutletContext<{ user: UserInfo | null }>()
  const { data: config } = useQuery({ queryKey: ['config-onboarding'], queryFn: fetchConfig })

  return (
    <div className="space-y-5">
      <section className="standard-panel surface-enter p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="section-kicker">First Run</div>
            <h2 className="section-title">欢迎进入 Kenne Index 工作台</h2>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-text-secondary">
              商业版默认模拟优先。完成交易所最小权限、预算纪律、实盘闸门和订阅认知后，再逐步启用更高风险能力。
            </p>
          </div>
          <Link to="/app/dashboard" className="primary-button w-fit px-5 py-3">
            进入仪表盘
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      <OnboardingChecklist user={user} config={config} />

      <section className="standard-panel p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 text-green" size={20} />
          <div>
            <h3 className="text-base font-semibold">默认安全策略</h3>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              模拟执行不会触发真实订单；实盘执行需要 Premium 权益、全局和租户级交易开关开启、用户二次确认、预算和单次限额校验全部通过。
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
