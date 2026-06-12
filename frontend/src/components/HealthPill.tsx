import { useQuery } from '@tanstack/react-query'
import { Activity } from 'lucide-react'
import { fetchHealth } from '../services/api'

export function healthTone(health?: { app?: string; database?: string; redis?: string }) {
  if (!health) return { label: '健康检查中', className: 'status-basic', dot: 'bg-orange' }
  if (health.app === 'ok' && health.database === 'ok') {
    return {
      label: health.redis === 'ok' ? '系统正常' : '核心正常 · Redis 降级',
      className: 'status-premium',
      dot: 'bg-green',
    }
  }
  return { label: '系统异常', className: 'status-basic', dot: 'bg-red' }
}

export default function HealthPill() {
  const { data } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 60_000,
  })
  const tone = healthTone(data)

  return (
    <div className={`glass-control flex w-fit items-center gap-2 px-4 py-3 text-xs text-text-secondary ${tone.className}`}>
      <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
      <Activity size={14} />
      {tone.label}
    </div>
  )
}
