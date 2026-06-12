import { Fragment, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Filter,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  confirmHistoryImport,
  fetchHistory,
  fetchHistoryStats,
  fetchMonthlyReport,
  fetchOperationAudit,
  historyExportUrl,
  initHistory,
  operationAuditExportUrl,
  previewHistoryImport,
} from '../services/api'
import type { TradeRecord } from '../types/api'

const PAGE_SIZE = 25

const statusLabel: Record<string, string> = {
  filled: 'LIVE',
  dry_run: 'SIM',
  failed: '失败',
  skipped: '跳过',
}

function statusClass(status: string) {
  if (status === 'filled') return 'border-green/30 bg-green/10 text-green'
  if (status === 'dry_run') return 'border-gray/30 bg-gray/10 text-gray'
  if (status === 'failed') return 'border-red/30 bg-red/10 text-red'
  return 'border-orange/30 bg-orange/10 text-orange'
}

function formatTime(value: string) {
  const source = value || ''
  return source.replace('T', ' ').substring(0, 16)
}

function HistoryPage() {
  const [month, setMonth] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [symbolFilter, setSymbolFilter] = useState('all')
  const [modeFilter, setModeFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [auditView, setAuditView] = useState<'trades' | 'operations'>('trades')
  const [operationPage, setOperationPage] = useState(1)
  const [operationRequestId, setOperationRequestId] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [actionError, setActionError] = useState('')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importMessage, setImportMessage] = useState('')

  const { data, isLoading, refetch, error } = useQuery({
    queryKey: ['history', month, startDate, endDate, statusFilter, symbolFilter, modeFilter, page],
    queryFn: () => fetchHistory({
      month: month || undefined,
      start_date: startDate || undefined,
      end_date: endDate || undefined,
      status: statusFilter,
      symbol: symbolFilter,
      mode: modeFilter,
      page,
      page_size: PAGE_SIZE,
    }),
  })
  const statsQuery = useQuery({
    queryKey: ['history-stats'],
    queryFn: fetchHistoryStats,
  })
  const operationQuery = useQuery({
    queryKey: ['operation-audit', operationPage, operationRequestId],
    queryFn: () => fetchOperationAudit({ page: operationPage, page_size: PAGE_SIZE, request_id: operationRequestId || undefined }),
    enabled: auditView === 'operations',
  })
  const reportQuery = useQuery({
    queryKey: ['monthly-report'],
    queryFn: fetchMonthlyReport,
  })
  const importPreview = useQuery({
    queryKey: ['history-import-preview', importFile?.name, importFile?.size],
    queryFn: () => importFile ? previewHistoryImport(importFile) : Promise.reject(new Error('未选择文件')),
    enabled: Boolean(importFile),
  })

  const records = data?.records || []
  const total = data?.total || 0
  const count = data?.count || 0
  const avg = count ? total / count : 0
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE))

  const chartData = useMemo(() => {
    const bySymbol = records.reduce<Record<string, number>>((acc, record) => {
      acc[record.symbol] = (acc[record.symbol] || 0) + record.usdt
      return acc
    }, {})
    return Object.entries(bySymbol)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([symbol, amount]) => ({ symbol, amount: Number(amount.toFixed(2)) }))
  }, [records])

  const modeStats = useMemo(() => {
    return records.reduce(
      (acc, record) => {
        if (record.status === 'filled') acc.live += record.usdt
        if (record.status === 'dry_run') acc.sim += record.usdt
        if (record.status === 'failed') acc.failed += 1
        return acc
      },
      { live: 0, sim: 0, failed: 0 },
    )
  }, [records])

  const clearHistory = async () => {
    setActionError('')
    if (!window.confirm('确认清空当前账户的开发测试执行历史？生产环境会拒绝此操作。')) return
    try {
      await initHistory()
      await refetch()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '清空历史失败')
    }
  }

  const importHistory = async () => {
    setImportMessage('')
    if (!importFile) {
      setImportMessage('请先选择 CSV 文件')
      return
    }
    try {
      const result = await confirmHistoryImport(importFile)
      setImportMessage(result.message)
      setImportFile(null)
      await refetch()
      await statsQuery.refetch()
      await reportQuery.refetch()
    } catch (err) {
      setImportMessage(err instanceof Error ? err.message : '导入失败')
    }
  }

  const exportCsv = () => {
    const header = [
      'ts',
      'created_at',
      'symbol',
      'exchange',
      'mode',
      'strategy_mode',
      'usdt',
      'price',
      'qty',
      'kenne_index',
      'mult',
      'momentum',
      'status',
      'order_id',
      'note',
    ]
    const rows = records.map((record) => header.map((field) => {
      const value = String(record[field as keyof TradeRecord] ?? '')
      return `"${value.replaceAll('"', '""')}"`
    }).join(','))
    const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `kenne-audit-${month || 'filtered'}-p${page}.csv`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const downloadServerCsv = (url: string) => {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = ''
    anchor.click()
  }

  const resetPage = (callback: () => void) => {
    setPage(1)
    callback()
  }

  return (
    <div className="space-y-5">
      <section className="standard-panel p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="section-kicker">Audit Trail</div>
            <h2 className="section-title">执行审计记录</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-text-secondary">
              所有模拟与实盘执行均由后端写入持久化审计表，记录策略、预算、订单结果和执行状态。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={() => refetch()} className="icon-button" title="刷新" aria-label="刷新">
              <RefreshCw size={15} className={isLoading ? 'animate-spin' : ''} />
            </button>
            <button onClick={exportCsv} disabled={records.length === 0} className="secondary-button px-3 py-2 text-xs disabled:opacity-50">
              <Download size={14} />
              导出当前页
            </button>
            <button onClick={() => downloadServerCsv(historyExportUrl())} className="secondary-button px-3 py-2 text-xs">
              <Download size={14} />
              导出全部交易
            </button>
            <button onClick={() => downloadServerCsv(operationAuditExportUrl())} className="secondary-button px-3 py-2 text-xs">
              <Download size={14} />
              导出操作审计
            </button>
            {import.meta.env.DEV && (
              <button onClick={clearHistory} className="danger-button">
                <Trash2 size={14} />
                开发清空
              </button>
            )}
          </div>
          <div className="flex rounded-xl border border-white/10 bg-white/[0.03] p-1">
            {[
              ['trades', '交易审计'],
              ['operations', '操作审计'],
            ].map(([value, label]) => (
              <button
                key={value}
                onClick={() => setAuditView(value as 'trades' | 'operations')}
                className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${auditView === value ? 'bg-white/12 text-white' : 'text-text-secondary hover:text-white'}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {auditView === 'trades' && <div className="mt-5 grid gap-2 md:grid-cols-2 xl:grid-cols-6">
          <label className="filter-control">
            <Filter size={13} />
            <select value={statusFilter} onChange={(event) => resetPage(() => setStatusFilter(event.target.value))}>
              <option value="all">全部状态</option>
              <option value="filled">实盘成交</option>
              <option value="dry_run">模拟执行</option>
              <option value="failed">失败</option>
              <option value="skipped">跳过</option>
            </select>
          </label>
          <label className="filter-control">
            <Search size={13} />
            <select value={symbolFilter} onChange={(event) => resetPage(() => setSymbolFilter(event.target.value))}>
              <option value="all">全部资产</option>
              <option value="BTC">BTC</option>
              <option value="ETH">ETH</option>
              <option value="SOL">SOL</option>
            </select>
          </label>
          <label className="filter-control">
            <Filter size={13} />
            <select value={modeFilter} onChange={(event) => resetPage(() => setModeFilter(event.target.value))}>
              <option value="all">全部模式</option>
              <option value="dry_run">SIM</option>
              <option value="live">LIVE</option>
            </select>
          </label>
          <label className="filter-control">
            <Calendar size={13} />
            <input value={month} onChange={(event) => resetPage(() => setMonth(event.target.value))} placeholder="YYYY-MM" />
          </label>
          <label className="filter-control">
            <Calendar size={13} />
            <input value={startDate} onChange={(event) => resetPage(() => setStartDate(event.target.value))} placeholder="开始 YYYY-MM-DD" />
          </label>
          <label className="filter-control">
            <Calendar size={13} />
            <input value={endDate} onChange={(event) => resetPage(() => setEndDate(event.target.value))} placeholder="结束 YYYY-MM-DD" />
          </label>
        </div>}
        {(error || actionError) && (
          <div className="mt-4 rounded-lg border border-red/30 bg-red/10 px-3 py-2 text-sm text-red">
            {actionError || (error instanceof Error ? error.message : '审计记录加载失败')}
          </div>
        )}
      </section>

      {auditView === 'trades' && (
        <section className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="standard-panel p-5">
            <div className="section-kicker">Audit Import</div>
            <h3 className="mt-1 text-base font-semibold">CSV 审计导入</h3>
            <p className="mt-2 text-sm leading-6 text-text-secondary">
              仅接受交易审计模板字段。导入前会预览缺列、错误资产和重复记录；确认后由后端写入持久化审计表。
            </p>
            <input
              className="mt-4 block w-full rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm"
              type="file"
              accept=".csv"
              onChange={(event) => {
                setImportMessage('')
                setImportFile(event.target.files?.[0] || null)
              }}
            />
            {importPreview.data && (
              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                <div className="metric-tile"><span>有效</span><strong>{importPreview.data.valid_count}</strong></div>
                <div className="metric-tile"><span>重复</span><strong>{importPreview.data.duplicate_count}</strong></div>
                <div className="metric-tile"><span>错误</span><strong>{importPreview.data.invalid_count}</strong></div>
              </div>
            )}
            {(importPreview.error || importMessage) && (
              <div className="mt-3 rounded-lg border border-orange/30 bg-orange/10 px-3 py-2 text-sm text-orange">
                {importMessage || (importPreview.error instanceof Error ? importPreview.error.message : '预览失败')}
              </div>
            )}
            <button
              onClick={importHistory}
              disabled={!importFile || Boolean(importPreview.data?.invalid_count)}
              className="secondary-button mt-4 px-4 py-3 disabled:opacity-50"
            >
              确认导入
            </button>
          </div>

          <div className="standard-panel p-5">
            <div className="section-kicker">Monthly Report</div>
            <h3 className="mt-1 text-base font-semibold">组合月度报表</h3>
            <p className="mt-2 text-xs leading-5 text-text-tertiary">{reportQuery.data?.disclaimer || '估算值，不构成会计、税务或投资建议。'}</p>
            <div className="mt-4 space-y-2">
              {(reportQuery.data?.months || []).slice(0, 4).map((item) => (
                <div key={item.month} className="metric-tile">
                  <span>{item.month} · {item.trade_count} 笔 · SIM ${item.sim_usdt.toFixed(2)} / LIVE ${item.live_usdt.toFixed(2)}</span>
                  <strong>${item.total_usdt.toFixed(2)}</strong>
                </div>
              ))}
              {(reportQuery.data?.months || []).length === 0 && (
                <div className="text-sm text-text-tertiary">暂无可生成报表的审计记录</div>
              )}
            </div>
          </div>
        </section>
      )}

      {auditView === 'operations' ? (
        <section className="standard-panel overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4">
            <h3 className="text-base font-semibold">系统操作审计</h3>
            <p className="mt-1 text-sm text-text-secondary">记录登录、配置、执行、回测、通知和任务等关键动作。</p>
            <label className="filter-control mt-4 max-w-md">
              <Search size={13} />
              <input
                value={operationRequestId}
                onChange={(event) => {
                  setOperationPage(1)
                  setOperationRequestId(event.target.value.trim())
                }}
                placeholder="按 Request ID 筛选"
              />
            </label>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>动作</th>
                  <th>结果</th>
                  <th>资源</th>
                  <th>Request ID</th>
                  <th>摘要</th>
                  <th>来源 IP</th>
                </tr>
              </thead>
              <tbody>
                {(operationQuery.data?.records || []).length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-text-tertiary">暂无操作审计记录</td>
                  </tr>
                ) : operationQuery.data?.records.map((record) => (
                  <tr key={record.id}>
                    <td className="font-mono text-xs">{formatTime(record.created_at)}</td>
                    <td className="font-mono text-xs">{record.action}</td>
                    <td>
                      <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${record.result === 'success' ? 'border-green/30 bg-green/10 text-green' : 'border-red/30 bg-red/10 text-red'}`}>
                        {record.result}
                      </span>
                    </td>
                    <td>{record.resource_type || '-'}</td>
                    <td className="font-mono text-xs">{record.request_id || '-'}</td>
                    <td>{record.summary || '-'}</td>
                    <td className="font-mono text-xs">{record.ip_address || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-col gap-3 border-t border-white/10 px-5 py-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
            <span>第 {operationPage} 页，共 {operationQuery.data?.count || 0} 条</span>
            <div className="flex items-center gap-2">
              <button className="secondary-button px-3 py-2 text-xs" disabled={operationPage <= 1} onClick={() => setOperationPage((value) => Math.max(1, value - 1))}>
                <ChevronLeft size={14} />
                上一页
              </button>
              <button
                className="secondary-button px-3 py-2 text-xs"
                disabled={operationPage >= Math.max(1, Math.ceil((operationQuery.data?.count || 0) / PAGE_SIZE))}
                onClick={() => setOperationPage((value) => value + 1)}
              >
                下一页
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </section>
      ) : (
        <>
      <section className="grid gap-3 md:grid-cols-4">
        {[
          ['记录数', count.toString()],
          ['累计预算消耗', `$${total.toFixed(2)}`],
          ['平均单笔', `$${avg.toFixed(2)}`],
          ['失败记录', modeStats.failed.toString()],
        ].map(([label, value]) => (
          <div key={label} className="standard-panel px-4 py-3">
            <div className="text-[11px] text-text-tertiary">{label}</div>
            <div className="mt-2 font-mono text-xl font-semibold tabular-nums">{value}</div>
          </div>
        ))}
      </section>

      {(statsQuery.data?.assets || []).length > 0 && (
        <section className="standard-panel p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold">资产维度汇总</h3>
            <span className="text-xs text-text-tertiary">浮动盈亏为估算值，不构成会计或税务记录</span>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {statsQuery.data?.assets.map((item) => (
              <div key={item.symbol} className="metric-tile">
                <span>{item.symbol} · 均价 ${item.avg_price.toLocaleString()}</span>
                <strong>${item.total_usdt.toFixed(2)}</strong>
                <span className="text-xs text-text-tertiary">数量 {item.total_qty.toFixed(8)} · SIM ${item.sim_usdt.toFixed(2)} · LIVE ${item.live_usdt.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="standard-panel p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold">当前筛选资产投入</h3>
            <span className="text-xs text-text-tertiary">按当前页记录统计</span>
          </div>
          <div className="h-44">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                  <XAxis dataKey="symbol" tick={{ fill: '#9ca3af', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 12 }} axisLine={false} tickLine={false} width={48} />
                  <Tooltip contentStyle={{ background: '#111316', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8 }} />
                  <Bar dataKey="amount" fill="#0a84ff" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-text-tertiary">暂无可视化数据</div>
            )}
          </div>
        </div>
        <div className="standard-panel p-5">
          <div className="section-kicker">SIM / LIVE</div>
          <h3 className="mt-1 text-base font-semibold">执行模式对比</h3>
          <div className="mt-4 space-y-3">
            <div className="metric-tile">
              <span>实盘成交金额</span>
              <strong>${modeStats.live.toFixed(2)}</strong>
            </div>
            <div className="metric-tile">
              <span>模拟执行金额</span>
              <strong>${modeStats.sim.toFixed(2)}</strong>
            </div>
          </div>
        </div>
      </section>

      <section className="standard-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>资产</th>
                <th>模式</th>
                <th>金额</th>
                <th>价格</th>
                <th>KI</th>
                <th>策略</th>
                <th>状态</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-text-tertiary">暂无执行记录</td>
                </tr>
              ) : records.map((record) => {
                const expanded = expandedId === record.id
                return (
                  <Fragment key={record.id}>
                    <tr key={record.id}>
                      <td className="font-mono text-xs">{formatTime(record.ts || record.created_at)}</td>
                      <td className="font-semibold">{record.symbol}</td>
                      <td>{record.mode === 'live' ? 'LIVE' : 'SIM'}</td>
                      <td>${record.usdt.toFixed(2)}</td>
                      <td>{record.price ? `$${record.price.toLocaleString()}` : '-'}</td>
                      <td>{record.kenne_index.toFixed(3)}</td>
                      <td className="font-mono text-xs">{record.strategy_mode}</td>
                      <td>
                        <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${statusClass(record.status)}`}>
                          {statusLabel[record.status] || record.status.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <button
                          className="icon-button h-8 w-8"
                          onClick={() => setExpandedId(expanded ? null : record.id)}
                          aria-label="展开详情"
                        >
                          <ChevronDown size={14} className={expanded ? 'rotate-180 transition' : 'transition'} />
                        </button>
                      </td>
                    </tr>
                    {expanded && (
                      <tr key={`${record.id}-detail`}>
                        <td colSpan={9} className="bg-white/[0.025]">
                          <div className="grid gap-3 p-4 text-xs md:grid-cols-4">
                            <div>
                              <span className="text-text-tertiary">订单号</span>
                              <div className="mt-1 font-mono">{record.order_id || '-'}</div>
                            </div>
                            <div>
                              <span className="text-text-tertiary">数量</span>
                              <div className="mt-1 font-mono">{record.qty.toFixed(8)}</div>
                            </div>
                            <div>
                              <span className="text-text-tertiary">动量</span>
                              <div className="mt-1">{record.momentum || '-'}</div>
                            </div>
                            <div>
                              <span className="text-text-tertiary">倍数</span>
                              <div className="mt-1 font-mono">{record.mult.toFixed(2)}x</div>
                            </div>
                            <div className="md:col-span-4">
                              <span className="text-text-tertiary">执行备注</span>
                              <div className="mt-1 leading-5">{record.note || '-'}</div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t border-white/10 px-5 py-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between">
          <span>第 {page} / {totalPages} 页，共 {count} 条</span>
          <div className="flex items-center gap-2">
            <button className="secondary-button px-3 py-2 text-xs" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
              <ChevronLeft size={14} />
              上一页
            </button>
            <button className="secondary-button px-3 py-2 text-xs" disabled={page >= totalPages} onClick={() => setPage((value) => Math.min(totalPages, value + 1))}>
              下一页
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      </section>
        </>
      )}
    </div>
  )
}

export default HistoryPage
