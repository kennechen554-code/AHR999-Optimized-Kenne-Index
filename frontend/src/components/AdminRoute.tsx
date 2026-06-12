import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

interface AdminRouteProps {
  children: React.ReactNode
}

export default function AdminRoute({ children }: AdminRouteProps) {
  const { user, authed, loading } = useAuth()

  // 若会话还在恢复中，挂起等待，避免在 user 为空时发生误判重定向
  if (loading) {
    return null
  }

  // 必须登录且角色为 admin 或 owner 才可以访问，否则强行重定向到用户仪表盘
  const isAuthorized = authed && user && (user.role === 'admin' || user.role === 'owner')

  if (!isAuthorized) {
    return <Navigate to="/app/dashboard" replace />
  }

  return <>{children}</>
}
