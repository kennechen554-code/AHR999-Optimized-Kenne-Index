import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowLeftRight,
  BarChart3,
  Clock,
  CreditCard,
  Database,
  FileText,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { logout } from '../services/api'
import type { UserInfo } from '../types/api'
import BrandWordmark from './BrandWordmark'
import HealthPill from './HealthPill'

interface LayoutProps {
  user: UserInfo | null
  onLogout: () => void
}

const NAV_ITEMS = [
  { to: '/app/dashboard', icon: LayoutDashboard, label: '仪表盘', main: true },
  { to: '/app/execute', icon: Zap, label: '执行', main: true },
  { to: '/app/history', icon: Clock, label: '审计', main: true },
  { to: '/app/settings', icon: Settings, label: '设置', main: true },
  { to: '/app/billing', icon: CreditCard, label: '订阅' },
  { to: '/app/backtest', icon: BarChart3, label: '回测', premium: true },
  { to: '/app/reports', icon: FileText, label: 'AI 报告', premium: true },
  { to: '/app/data-rights', icon: Database, label: '数据' },
  { to: '/app/mfa', icon: ShieldCheck, label: 'MFA' },
]

const planLabel: Record<string, string> = {
  free: 'Free',
  basic: 'Basic',
  premium: 'Premium',
}

function Layout({ user, onLogout }: LayoutProps) {
  const navigate = useNavigate()
  const [isMoreOpen, setIsMoreOpen] = useState(false)
  const isPremium = user?.plan === 'premium'
  const backtestUnlocked = Boolean(user?.entitlements.backtesting || isPremium)
  const aiReportUnlocked = Boolean(user?.entitlements.ai_daily_report || isPremium)

  const handleLogout = async () => {
    await logout()
    onLogout()
    navigate('/')
  }

  const renderNavItem = (compact = false) => {
    const filteredItems = compact ? NAV_ITEMS.filter((item) => item.main) : NAV_ITEMS

    return filteredItems.map(({ to, icon: Icon, label, premium }) => {
      let locked = false
      if (premium) {
        if (to === '/app/backtest') locked = !backtestUnlocked
        else if (to === '/app/reports') locked = !aiReportUnlocked
        else locked = !isPremium
      }
      return (
        <NavLink
          key={to}
          to={to}
          title={locked ? `${label} · Premium 解锁` : label}
          onClick={() => {
            if (compact) setIsMoreOpen(false)
          }}
          className={({ isActive }) => {
            if (compact) {
              return `dock-item ${isActive ? 'dock-item-active' : ''} ${locked ? 'dock-item-locked' : ''}`
            }
            return `sidebar-link ${isActive ? 'sidebar-link-active' : ''} ${locked ? 'sidebar-link-locked' : ''}`
          }}
        >
          <Icon size={compact ? 19 : 20} />
          <span>{label}</span>
          {!compact && locked && <LockKeyhole size={14} className="ml-auto text-orange" />}
        </NavLink>
      )
    })
  }

  const renderMoreItems = () => {
    const itemsToRender = NAV_ITEMS.filter((item) => !item.main)

    return itemsToRender.map(({ to, icon: Icon, label, premium }) => {
      let locked = false
      if (premium) {
        if (to === '/app/backtest') locked = !backtestUnlocked
        else if (to === '/app/reports') locked = !aiReportUnlocked
        else locked = !isPremium
      }
      return (
        <NavLink
          key={to}
          to={to}
          onClick={() => setIsMoreOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl border border-white/5 bg-white/[0.04] p-3 text-sm font-semibold transition hover:bg-white/[0.08] ${isActive ? 'border-accent/30 bg-accent/10 text-accent' : 'text-text-secondary'}`
          }
        >
          <Icon size={16} />
          <span className="truncate">{label}</span>
          {locked && <LockKeyhole size={12} className="ml-auto text-orange" />}
        </NavLink>
      )
    })
  }

  return (
    <div className="app-shell text-text-primary">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <NavLink to="/app/dashboard" className="block">
            <BrandWordmark caption="专业级 DCA 信号与执行系统" />
          </NavLink>
        </div>

        <nav className="sidebar-nav" aria-label="工作台功能区">
          {renderNavItem(false)}
        </nav>

        <div className="sidebar-user">
          <div className="glass-control p-4">
            {user && (user.role === 'admin' || user.role === 'owner') && (
              <NavLink
                to="/admin/ops"
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-orange/20 bg-orange/5 py-2.5 text-xs font-semibold text-orange transition hover:bg-orange/10 mb-3"
              >
                <ArrowLeftRight size={13} />
                管理控制台
              </NavLink>
            )}
            <div className="flex items-center gap-2 text-xs text-text-tertiary">
              <Activity size={14} className="text-accent" />
              {user?.tenant?.name || '个人工作区'}
            </div>
            <div className="mt-2 truncate text-sm font-semibold">{user?.display_name || 'Kenne User'}</div>
            <div className="mt-1 truncate text-xs text-text-tertiary">{user?.email}</div>
            <div className="mt-4 flex items-center justify-between gap-2">
              <span className={`status-pill ${isPremium ? 'status-premium' : 'status-basic'}`}>
                <ShieldCheck size={13} />
                {planLabel[user?.plan || 'free']}
              </span>
              <button onClick={handleLogout} className="icon-button" title="退出登录" aria-label="退出登录">
                <LogOut size={16} />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <header className="mobile-topbar">
        <NavLink to="/app/dashboard" className="min-w-0">
          <BrandWordmark caption="Professional DCA Desk" compact />
        </NavLink>
        <div className="flex items-center gap-2">
          <span className={`status-pill ${isPremium ? 'status-premium' : 'status-basic'}`}>
            {planLabel[user?.plan || 'free']}
          </span>
          <button onClick={handleLogout} className="icon-button" title="退出登录" aria-label="退出登录">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="app-content">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm text-text-tertiary">
                <Activity size={15} className="text-accent" />
                {user?.tenant?.name || '个人工作区'} · {user?.email}
              </div>
              <h1 className="page-title mt-2">投资信号工作台</h1>
            </div>
            <HealthPill />
          </div>
          <Outlet context={{ user }} />
        </div>
      </main>

      <nav className="mobile-dock" aria-label="移动功能区">
        {renderNavItem(true)}
        <button
          onClick={() => setIsMoreOpen(!isMoreOpen)}
          className={`dock-item ${isMoreOpen ? 'dock-item-active' : ''}`}
          title="更多菜单"
          aria-label="更多菜单"
        >
          <Menu size={19} />
          <span>更多</span>
        </button>
      </nav>

      {/* 移动端“更多”菜单遮罩 */}
      <div
        className={`mobile-more-overlay ${isMoreOpen ? 'mobile-more-overlay-show' : ''}`}
        onClick={() => setIsMoreOpen(false)}
      />

      {/* 移动端“更多”菜单抽屉 */}
      <div className={`mobile-more-drawer ${isMoreOpen ? 'mobile-more-drawer-show' : ''}`}>
        <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-tertiary">更多功能</div>
          <button
            onClick={() => setIsMoreOpen(false)}
            className="text-xs text-text-tertiary hover:text-white"
          >
            关闭
          </button>
        </div>
        
        <div className="grid grid-cols-2 gap-2">
          {renderMoreItems()}
        </div>

        {user && (user.role === 'admin' || user.role === 'owner') && (
          <div className="mt-3">
            <NavLink
              to="/admin/ops"
              onClick={() => setIsMoreOpen(false)}
              className="flex items-center justify-center gap-2 rounded-xl border border-orange/20 bg-orange/5 py-3 text-sm font-semibold text-orange hover:bg-orange/10 transition w-full"
            >
              <ArrowLeftRight size={14} />
              进入管理员后台
            </NavLink>
          </div>
        )}
        
        {/* 用户与退出登录区域 */}
        <div className="mt-4 border-t border-white/10 pt-4 flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] text-text-tertiary">
              <Activity size={12} className="text-accent" />
              <span className="truncate">{user?.tenant?.name || '个人工作区'}</span>
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-text-primary">{user?.display_name || 'Kenne User'}</div>
            <div className="mt-0.5 truncate text-[11px] text-text-tertiary">{user?.email}</div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`status-pill ${isPremium ? 'status-premium' : 'status-basic'} px-2.5 py-1 text-[11px]`}>
              {planLabel[user?.plan || 'free']}
            </span>
            <button
              onClick={async () => {
                setIsMoreOpen(false)
                await handleLogout()
              }}
              className="icon-button h-9 w-9 rounded-xl flex items-center justify-center bg-red/10 border-red/20 text-red hover:bg-red/20"
              title="退出登录"
              aria-label="退出登录"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Layout
