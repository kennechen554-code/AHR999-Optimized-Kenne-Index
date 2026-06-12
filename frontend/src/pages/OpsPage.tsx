import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Database, ShieldCheck } from 'lucide-react'
import { fetchHealthDetail, fetchOperationAudit, fetchRetentionPolicy, fetchRiskEvents, fetchTaskRuns, resolveRiskEvent, runRetentionCleanup } from '../services/api'
import type { LucideIcon } from 'lucide-react'

interface HealthMetric {
  label: string
  value: string
  Icon: LucideIcon
}

export default function OpsPage() {
  const health = useQuery({ queryKey: ['health-detail'], queryFn: fetchHealthDetail })
  const taskRuns = useQuery({ queryKey: ['ops-task-runs'], queryFn: () => fetchTaskRuns(1) })
  const audit = useQuery({ queryKey: ['ops-failed-audit'], queryFn: () => fetchOperationAudit({ result: 'failed', page_size: 10 }) })
  const risk = useQuery({ queryKey: ['risk-events'], queryFn: fetchRiskEvents })
  const retention = useQuery({ queryKey: ['retention-policy'], queryFn: fetchRetentionPolicy })

  const cleanup = async () => {
    await runRetentionCleanup()
    await Promise.all([audit.refetch(), taskRuns.refetch(), risk.refetch()])
  }

  const healthMetrics: HealthMetric[] = [
    { label: 'Database', value: health.data?.database || 'unknown', Icon: Database },
    { label: 'Redis', value: health.data?.redis || 'unknown', Icon: Activity },
    { label: 'Stripe Webhook', value: health.data?.stripe_webhook ? 'ready' : 'missing', Icon: ShieldCheck },
    { label: 'SMTP', value: health.data?.system_smtp ? 'ready' : 'missing', Icon: ShieldCheck },
  ]

  return (
    <div className="space-y-5">
      <section className="standard-panel p-5">
        <div className="section-kicker">Tenant Ops</div>
        <h2 className="section-title">管理员运维面板</h2>
        <p className="mt-2 text-sm leading-6 text-text-secondary">聚合健康检查、任务运行、失败审计、风险事件与保留策略。</p>
      </section>

      <section className="grid gap-3 md:grid-cols-4">
        {healthMetrics.map(({ label, value, Icon }) => (
          <div key={label} className="standard-panel px-4 py-3">
            <div className="flex items-center gap-2 text-xs text-text-tertiary"><Icon size={14} className="text-accent" />{label}</div>
            <div className="mt-2 font-mono text-xl font-semibold">{value}</div>
          </div>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="standard-panel p-5">
          <h3 className="text-base font-semibold">最近任务运行</h3>
          <div className="mt-3 space-y-2">
            {(taskRuns.data?.records || []).slice(0, 6).map((run) => (
              <div key={run.id} className="metric-tile">
                <span>{run.task_type} · {run.message || '-'}</span>
                <strong>{run.status}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="standard-panel p-5">
          <h3 className="text-base font-semibold">失败操作审计</h3>
          <div className="mt-3 space-y-2">
            {(audit.data?.records || []).map((record) => (
              <Link key={record.id} to={`/app/history?request_id=${encodeURIComponent(record.request_id)}`} className="metric-tile">
                <span>{record.action} · {record.request_id || '-'}</span>
                <strong>{record.result}</strong>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="standard-panel p-5">
        <div className="flex items-center gap-2">
          <AlertTriangle className="text-orange" size={18} />
          <h3 className="text-base font-semibold">风险事件</h3>
        </div>
        <div className="mt-3 grid gap-2">
          {(risk.data?.events || []).map((event) => (
            <div key={event.id} className="metric-tile">
              <span>{event.severity} · {event.event_type} · {event.summary}</span>
              <button className="secondary-button px-3 py-2 text-xs" disabled={Boolean(event.resolved_at)} onClick={() => resolveRiskEvent(event.id).then(() => risk.refetch())}>
                {event.resolved_at ? '已处理' : '标记处理'}
              </button>
            </div>
          ))}
          {(risk.data?.events || []).length === 0 && <div className="text-sm text-text-tertiary">暂无风险事件</div>}
        </div>
      </section>

      <section className="standard-panel p-5">
        <h3 className="text-base font-semibold">保留策略</h3>
        <p className="mt-2 text-sm text-text-secondary">
          Operation audit {retention.data?.operation_audit_days ?? '-'} 天 · Task runs {retention.data?.task_run_days ?? '-'} 天 · Risk events {retention.data?.risk_event_days ?? '-'} 天
        </p>
        <button onClick={cleanup} className="secondary-button mt-4 px-4 py-3">运行保留清理</button>
      </section>
    </div>
  )
}
