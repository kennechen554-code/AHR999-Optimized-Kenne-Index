import { useSearchParams, Link, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Zap,
  Gift,
  Coins,
} from 'lucide-react'
import { fetchInviteInfo } from '../services/api'
import type { InviteInfo } from '../types/api'

export default function ShareCardPage() {
  const [searchParams] = useSearchParams()
  const code = searchParams.get('code') || ''

  // 若无推荐码，直接重定向到主注册页
  if (!code) {
    return <Navigate to="/login?action=register" replace />
  }

  // 匿名获取邀请人基本信息
  const { data: inviteInfo, isLoading, error } = useQuery<InviteInfo>({
    queryKey: ['inviteInfo', code],
    queryFn: () => fetchInviteInfo(code),
    enabled: Boolean(code),
  })

  return (
    <div className="min-h-screen bg-bg text-text-primary selection:bg-accent/30 selection:text-white flex flex-col justify-between relative overflow-hidden">
      {/* 背景流光 */}
      <div className="absolute top-[-20%] left-[-20%] w-[60%] h-[60%] rounded-full bg-accent/10 blur-[180px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-20%] w-[60%] h-[60%] rounded-full bg-indigo-500/10 blur-[180px] pointer-events-none" />

      {/* 头部微导航 */}
      <header className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 flex items-center justify-between border-b border-white/5 bg-transparent">
        <div className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-accent to-indigo-600 text-white font-black text-lg">
            K
          </span>
          <span className="bg-gradient-to-r from-white to-text-secondary bg-clip-text text-lg font-bold text-transparent">
            Kenne Index
          </span>
        </div>
        <Link
          to="/market"
          className="text-xs font-semibold text-accent hover:underline flex items-center gap-1"
        >
          查看公开大盘指标
          <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      {/* 主面板 */}
      <main className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-xl space-y-8">
          
          {isLoading ? (
            <div className="glass-panel p-12 text-center border-white/5">
              <span className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent mb-3" />
              <p className="text-sm text-text-secondary">正在连线生成专属定投卡片...</p>
            </div>
          ) : error ? (
            <div className="glass-panel p-8 text-center border-red/10 bg-red/5">
              <p className="text-red font-semibold mb-4">卡片失效或推荐人信息不存在</p>
              <Link
                to="/login?action=register"
                className="inline-flex items-center justify-center rounded-xl bg-accent px-5 py-2.5 text-sm font-bold text-white"
              >
                直接去注册
              </Link>
            </div>
          ) : inviteInfo ? (
            <div className="space-y-6">
              
              {/* 好友邀请标语 */}
              <div className="text-center space-y-2">
                <div className="inline-flex items-center gap-1 rounded-full bg-accent/15 border border-accent/20 px-3 py-1 text-xs font-semibold text-accent mb-2">
                  <Gift className="h-3.5 w-3.5" />
                  专属邀请福利：首充赠送 7 天 Premium 试用
                </div>
                <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
                  您的好友 <span className="text-accent">{inviteInfo.referrer_name}</span> 邀您加入
                </h1>
                <p className="text-sm text-text-secondary max-w-md mx-auto">
                  他/她正在使用 Kenne Index 进行加密货币智能防爆仓定投，并为您争取到了专享额度。
                </p>
              </div>

              {/* 定投成就卡片（高光） */}
              <div className="relative rounded-3xl border border-white/10 bg-gradient-to-b from-white/[0.04] to-white/[0.01] p-8 backdrop-blur-md shadow-2xl overflow-hidden group">
                <div className="absolute top-0 right-0 h-32 w-32 bg-accent/5 rounded-bl-[100px] pointer-events-none" />
                
                <div className="text-center space-y-6">
                  <div>
                    <span className="text-xs text-text-secondary font-medium tracking-wider uppercase block">
                      定投表现 · 累计收益率
                    </span>
                    <div className="mt-2 text-5xl sm:text-6xl font-black tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent animate-pulse">
                      +{inviteInfo.profit_rate}%
                    </div>
                  </div>

                  <div className="flex justify-center gap-8 border-t border-white/5 pt-6 text-sm">
                    <div className="text-center">
                      <span className="text-text-secondary text-xs block mb-1">推荐裂变伙伴</span>
                      <span className="font-bold text-white text-base">{inviteInfo.invited_count} 位</span>
                    </div>
                    <div className="w-px bg-white/5" />
                    <div className="text-center">
                      <span className="text-text-secondary text-xs block mb-1">安全护航引擎</span>
                      <span className="font-bold text-accent text-base flex items-center gap-1">
                        <ShieldCheck className="h-4 w-4 text-emerald-400" />
                        Kenne Index
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 行为引导按钮 */}
              <div className="space-y-4">
                <Link
                  to={`/login?action=register&code=${code}`}
                  className="group w-full flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-accent to-indigo-600 py-4 font-bold text-white shadow-xl shadow-accent/25 hover:scale-101 hover:shadow-accent/35 active:scale-99 transition-all text-base"
                >
                  接受邀请，开启智能定投
                  <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-0.5" />
                </Link>
                
                <div className="flex justify-between items-center text-xs text-text-secondary px-2">
                  <span className="flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5 text-accent" /> 极速绑定 API
                  </span>
                  <span className="flex items-center gap-1">
                    <Coins className="h-3.5 w-3.5 text-indigo-400" /> 100% 资金安全自托管
                  </span>
                </div>
              </div>

            </div>
          ) : null}

        </div>
      </main>

      {/* 底部免责声明 */}
      <footer className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 text-center text-xs text-text-secondary border-t border-white/5">
        加密货币投资有极高风险，定投战绩仅代表历史参考，不构成财务投资建议。
      </footer>
    </div>
  )
}
