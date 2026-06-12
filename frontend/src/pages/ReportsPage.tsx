import React, { useEffect, useState } from 'react'
import { useNavigate, useOutletContext } from 'react-router-dom'
import { FileText, LockKeyhole, Sparkles, AlertTriangle, ArrowRight, RefreshCw } from 'lucide-react'
import { fetchAiDailyReport } from '../services/api'
import type { AiDailyReportResponse, UserInfo } from '../types/api'

export default function ReportsPage() {
  const navigate = useNavigate()
  const { user } = useOutletContext<{ user: UserInfo | null }>()
  const isPremium = user?.plan === 'premium'

  const [report, setReport] = useState<AiDailyReportResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isPremium) {
      loadReport()
    }
  }, [isPremium])

  const loadReport = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAiDailyReport()
      setReport(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载 AI 日报失败')
    } finally {
      setLoading(false)
    }
  }

  // 引导升级页面
  if (!isPremium) {
    return (
      <div className="mx-auto max-w-3xl py-8 px-4">
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-8 md:p-12 shadow-2xl backdrop-blur-xl">
          <div className="relative flex flex-col items-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-orange/10 text-orange shadow-inner">
              <LockKeyhole size={32} />
            </div>

            <span className="mt-6 status-pill status-premium px-3 py-1 font-semibold flex items-center gap-1">
              <Sparkles size={12} />
              PREMIUM 会员专属
            </span>

            <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-text-primary">
              AI 智能日报 · 自动推送
            </h1>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-text-tertiary">
              每 2 分钟深度扫描多源行情与链上估值，利用精准的量化策略模型输出定投操作指令与风险水位，助您掌控每次长期配置契机。
            </p>

            {/* 核心权益卡片 */}
            <div className="mt-8 grid w-full gap-4 sm:grid-cols-2 text-left">
              <div className="glass-panel p-5 border border-white/5 rounded-2xl">
                <h3 className="font-semibold text-text-primary text-sm flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-orange" />
                  每 2 分钟实时扫描
                </h3>
                <p className="mt-1 text-xs text-text-tertiary leading-relaxed">
                  系统定时执行 dca_report 任务，24小时不间断为您解析盘面波动。
                </p>
              </div>

              <div className="glass-panel p-5 border border-white/5 rounded-2xl">
                <h3 className="font-semibold text-text-primary text-sm flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  多因子复合估值
                </h3>
                <p className="mt-1 text-xs text-text-tertiary leading-relaxed">
                  融合改进版 AHR999 指数、幂律趋势线偏离度与动量折扣系数。
                </p>
              </div>

              <div className="glass-panel p-5 border border-white/5 rounded-2xl">
                <h3 className="font-semibold text-text-primary text-sm flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                  策略风控红线
                </h3>
                <p className="mt-1 text-xs text-text-tertiary leading-relaxed">
                  基于严格防守或平衡收益策略计算各币种定投权重，控制回撤。
                </p>
              </div>

              <div className="glass-panel p-5 border border-white/5 rounded-2xl">
                <h3 className="font-semibold text-text-primary text-sm flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-blue" />
                  智能执行决策
                </h3>
                <p className="mt-1 text-xs text-text-tertiary leading-relaxed">
                  对 BTC、ETH、SOL 的操作级别进行分档定位，清晰指引资产仓位配置。
                </p>
              </div>
            </div>

            <button
              onClick={() => navigate('/app/billing')}
              className="mt-8 flex w-full items-center justify-center gap-2 rounded-xl bg-orange px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-orange/20 transition-all hover:bg-orange-dark hover:scale-[1.01]"
            >
              升级为专业版解锁此功能
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  // 加载状态
  if (loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <RefreshCw className="animate-spin text-accent" size={28} />
        <span className="text-sm text-text-secondary font-medium">正在读取最新 AI 报告...</span>
      </div>
    )
  }

  // 异常态
  if (error) {
    return (
      <div className="mx-auto max-w-3xl py-8 px-4">
        <div className="glass-panel rounded-2xl border border-red-500/10 p-6 text-center text-sm text-red-400">
          <AlertTriangle className="mx-auto mb-2 text-red-500" size={28} />
          <p className="font-semibold">{error}</p>
          <button
            onClick={loadReport}
            className="mt-4 rounded-lg bg-white/5 border border-white/10 px-4 py-2 hover:bg-white/10 text-xs font-semibold text-text-primary transition-all"
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  // 空态
  if (!report) {
    return (
      <div className="mx-auto max-w-3xl py-8 px-4">
        <div className="glass-panel rounded-2xl p-8 text-center text-sm text-text-tertiary">
          <FileText className="mx-auto mb-3 text-text-tertiary/40" size={32} />
          <p>暂无报告，系统正在定时生成中</p>
          <button
            onClick={loadReport}
            className="mt-4 rounded-lg bg-white/5 border border-white/10 px-4 py-2 hover:bg-white/10 text-xs font-semibold text-text-primary transition-all"
          >
            手动刷新
          </button>
        </div>
      </div>
    )
  }

  // 正常展示
  return (
    <div className="mx-auto max-w-3xl py-6 px-4">
      {/* 报表卡片面板 */}
      <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/[0.02] shadow-xl backdrop-blur-lg">
        {/* 页眉头图 */}
        <div className="relative border-b border-white/10 bg-gradient-to-r from-accent/10 to-orange/5 p-6 sm:p-8">
          <div className="absolute right-6 top-6 rounded-full bg-green-500/10 px-2.5 py-1 text-xs font-semibold text-green-400 flex items-center gap-1.5 border border-green-500/20">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-400" />
            自动定投已就绪
          </div>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent">
              <FileText size={24} />
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-text-primary">DCA 智能运行日报</h2>
              <p className="mt-1 text-xs text-text-tertiary">最后同步生成时间：{report.generated_at}</p>
            </div>
          </div>
        </div>

        {/* 报表主体渲染 */}
        <div className="p-6 sm:p-8">
          <SimpleMarkdownRenderer content={report.content} />
        </div>

        {/* 页脚底图 */}
        <div className="border-t border-white/5 bg-white/[0.01] px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs text-text-tertiary">
          <span>提醒：数据均由本地 Hermes Agent 自动定投服务渲染。</span>
          <button
            onClick={loadReport}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-white/5 border border-white/10 px-3 py-1.5 hover:bg-white/10 text-text-primary transition-all active:scale-[0.98]"
          >
            <RefreshCw size={12} />
            手动刷新报告
          </button>
        </div>
      </div>
    </div>
  )
}

// 简易 Markdown 渲染组件，避开 peer-dep 冲突并渲染出极佳效果
function SimpleMarkdownRenderer({ content }: { content: string }) {
  const lines = content.split('\n')
  const elements: React.ReactNode[] = []

  let inTable = false
  let tableHeaders: string[] = []
  let tableRows: string[][] = []

  const flushTable = (key: number) => {
    if (tableRows.length > 0 || tableHeaders.length > 0) {
      elements.push(
        <div key={`table-${key}`} className="overflow-x-auto my-6 border border-white/5 rounded-xl bg-white/[0.01] p-1">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.02]">
                {tableHeaders.map((h, i) => (
                  <th key={`${h}-${i}`} className="px-4 py-3 font-semibold text-text-primary">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tableRows.map((row, idx) => (
                <tr key={`row-${idx}-${row.join('|')}`} className="border-b border-white/5 last:border-0 hover:bg-white/[0.01] transition-colors">
                  {row.map((cell, cidx) => (
                    <td key={`${cell}-${cidx}`} className="px-4 py-3 text-text-secondary">{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      tableHeaders = []
      tableRows = []
    }
    inTable = false
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()

    // 1. 处理表格
    if (line.startsWith('|')) {
      inTable = true
      const cells = line.split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
      if (line.includes('---')) {
        continue
      }
      if (tableHeaders.length === 0) {
        tableHeaders = cells
      } else {
        tableRows.push(cells)
      }
      continue
    } else {
      if (inTable) {
        flushTable(i)
      }
    }

    // 2. 处理大标题 #
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={i} className="text-xl font-bold text-text-primary mt-6 mb-4 border-b border-white/10 pb-2 flex items-center gap-2">
          {line.replace('# ', '')}
        </h1>
      )
      continue
    }

    // 3. 处理中标题 ##
    if (line.startsWith('## ')) {
      elements.push(
        <h2 key={i} className="text-base font-bold text-text-primary mt-6 mb-3 flex items-center gap-2">
          {line.replace('## ', '')}
        </h2>
      )
      continue
    }

    // 4. 处理分割线 ---
    if (line === '---') {
      elements.push(<hr key={i} className="my-6 border-white/10" />)
      continue
    }

    // 5. 处理列表 -
    if (line.startsWith('- ')) {
      const cleanLine = line.replace('- ', '')
      elements.push(
        <li key={i} className="ml-5 list-disc my-1.5 text-xs text-text-secondary leading-relaxed">
          {renderTextWithBold(cleanLine)}
        </li>
      )
      continue
    }

    // 6. 处理普通行
    if (line !== '') {
      elements.push(
        <p key={i} className="my-2 text-xs text-text-secondary leading-relaxed">
          {renderTextWithBold(line)}
        </p>
      )
    }
  }

  if (inTable) {
    flushTable(lines.length)
  }

  return <div className="space-y-1">{elements}</div>
}

function renderTextWithBold(text: string) {
  const parts = text.split('**')
  return parts.map((part, index) => {
    if (index % 2 === 1) {
      return <strong key={`${part}-${index}`} className="font-semibold text-text-primary bg-white/5 px-1 py-0.5 rounded">{part}</strong>
    }
    return part
  })
}
