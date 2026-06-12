import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowLeftRight,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldAlert,
  Users,
} from 'lucide-react'
import { logout } from '../services/api'
import type { UserInfo } from '../types/api'
import BrandWordmark from './BrandWordmark'
import HealthPill from './HealthPill'

interface AdminLayoutProps {
  user: UserInfo | null
  onLogout: () => void
}

const ADMIN_NAV_ITEMS = [
  { to: '/admin/ops', icon: Activity, label: '系统运维' },
  { to: '/admin/team', icon: Users, label: '团队与成员' },
]

export default function AdminLayout({ user, onLogout }: AdminLayoutProps) {
  const navigate = useNavigate()
  const [isMoreOpen, setIsMoreOpen] = useState(false)

  const handleLogout = async () => {
    await logout()
    onLogout()
    navigate('/')
  }

  const renderNavItem = (compact = false) => {
    return ADMIN_NAV_ITEMS.map(({ to, icon: Icon, label }) => (
      <NavLink
        key={to}
        to={to}
        onClick={() => {
          if (compact) setIsMoreOpen(false)
        }}
        className={({ isActive }) => {
          if (compact) {
            return `dock-item ${isActive ? 'dock-item-active' : ''}`
          }
          return `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`
        }}
      >
        <Icon size={compact ? 19 : 20} />
        <span>{label}</span>
      </NavLink>
    ))
  }

  return (
    <div className="app-shell text-text-primary admin-shell-theme">
      {/* 侧边栏 */}
      <aside className="app-sidebar border-r border-orange/10 bg-gradient-to-b from-[#16121a] to-[#0d0a10]">
        <div className="sidebar-brand">
          <NavLink to="/admin/ops" className="block">
            <BrandWordmark caption="平台管理控制台" />
          </NavLink>
        </div>

        <div className="px-4 py-2">
          <div className="glass-control border-orange/20 bg-orange/5 px-3 py-2 text-xs font-semibold flex items-center gap-2 text-orange">
            <ShieldAlert size={14} />
            管理员专区 (高权限)
          </div>
        </div>

        <nav className="sidebar-nav mt-2" aria-label="管理后台功能区">
          {renderNavItem(false)}
        </nav>

        {/* 底部视图切换与用户区 */}
        <div className="sidebar-user mt-auto">
          <div className="glass-control p-4">
            <NavLink
              to="/app/dashboard"
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-accent/20 bg-accent/5 py-2.5 text-xs font-semibold text-accent transition hover:bg-accent/10"
            >
              <LayoutDashboard size={14} />
              返回用户工作台
            </NavLink>

            <div className="mt-4 border-t border-white/5 pt-3">
              <div className="flex items-center gap-2 text-xs text-text-tertiary">
                <Activity size={14} className="text-orange" />
                {user?.tenant?.name || '管理工作区'}
              </div>
              <div className="mt-2 truncate text-sm font-semibold text-orange">{user?.display_name || 'Admin'}</div>
              <div className="mt-1 truncate text-xs text-text-tertiary">{user?.email}</div>
              <div className="mt-4 flex items-center justify-between">
                <span className="status-pill status-premium border-orange/30 bg-orange/10 text-orange">
                  SYSTEM ADMIN
                </span>
                <button onClick={handleLogout} className="icon-button" title="退出登录" aria-label="退出登录">
                  <LogOut size={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* 移动端顶部栏 */}
      <header className="mobile-topbar border-b border-orange/10 bg-[#16121a]">
        <NavLink to="/admin/ops" className="min-w-0">
          <BrandWordmark caption="Admin Panel" compact />
        </NavLink>
        <div className="flex items-center gap-2">
          <span className="status-pill border-orange/30 bg-orange/10 text-orange text-[10px] px-2 py-0.5 font-bold">
            ADMIN
          </span>
          <button onClick={handleLogout} className="icon-button" title="退出登录" aria-label="退出登录">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* 主视图 */}
      <main className="app-main">
        <div className="app-content">
          <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-sm text-text-tertiary">
                <ShieldAlert size={15} className="text-orange" />
                {user?.tenant?.name || '系统工作区'} · {user?.email}
              </div>
              <h1 className="page-title mt-2">系统运维与管理后台</h1>
            </div>
            <HealthPill />
          </div>
          <Outlet context={{ user }} />
        </div>
      </main>

      {/* 移动端导航 Dock */}
      <nav className="mobile-dock border-t border-orange/10 bg-[#0d0a10]" aria-label="管理后台移动区">
        {renderNavItem(true)}
        <button
          onClick={() => setIsMoreOpen(!isMoreOpen)}
          className={`dock-item ${isMoreOpen ? 'dock-item-active' : ''}`}
          title="更多菜单"
          aria-label="更多菜单"
        >
          <Menu size={19} />
          <span>菜单</span>
        </button>
      </nav>

      {/* 移动端“更多”菜单抽屉 */}
      <div
        className={`mobile-more-overlay ${isMoreOpen ? 'mobile-more-overlay-show' : ''}`}
        onClick={() => setIsMoreOpen(false)}
      />
      <div className={`mobile-more-drawer ${isMoreOpen ? 'mobile-more-drawer-show' : ''} bg-[#16121a]`}>
        <div className="flex items-center justify-between mb-4 border-b border-white/5 pb-2">
          <div className="text-xs font-semibold uppercase tracking-wider text-orange">管理员后台快捷操作</div>
          <button onClick={() => setIsMoreOpen(false)} className="text-xs text-text-tertiary hover:text-white">
            关闭
          </button>
        </div>

        <div className="space-y-3">
          <NavLink
            to="/app/dashboard"
            onClick={() => setIsMoreOpen(false)}
            className="flex items-center justify-center gap-2 rounded-xl border border-accent/20 bg-accent/5 py-3 text-sm font-semibold text-accent hover:bg-accent/10 transition w-full"
          >
            <LayoutDashboard size={16} />
            返回用户工作台
          </NavLink>
        </div>

        <div className="mt-4 border-t border-white/10 pt-4 flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] text-text-tertiary">
              <Activity size={12} className="text-orange" />
              <span className="truncate">{user?.tenant?.name || '管理工作区'}</span>
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-orange">{user?.display_name || 'Admin'}</div>
          </div>
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
  )
}
