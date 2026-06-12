import type { TaskRunLog } from '../types/api'

interface TaskRunTimelineProps {
  runs: TaskRunLog[]
}

function formatTime(value: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

export default function TaskRunTimeline({ runs }: TaskRunTimelineProps) {
  if (runs.length === 0) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-text-tertiary">
        暂无自动化运行记录。启用 dry-run 任务后，最近运行会显示在这里。
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>任务</th>
            <th>状态</th>
            <th>消息</th>
            <th>开始时间</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>{run.task_type}</td>
              <td>
                <span className={run.status === 'success' ? 'text-green' : run.status === 'failed' ? 'text-red' : 'text-orange'}>
                  {run.status}
                </span>
              </td>
              <td>{run.message || '-'}</td>
              <td>{formatTime(run.started_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
