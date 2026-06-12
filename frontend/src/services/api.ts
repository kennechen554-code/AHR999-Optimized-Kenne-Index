import type {
  DcaRunResult,
  HistoryResponse,
  MvrvData,
  PlansResponse,
  Signal,
  StrategiesResponse,
  TokenResponse,
  UserConfig,
  UserInfo,
  BacktestResult,
  LocalDatasetsResponse,
  HistoryStatsResponse,
  OperationAuditResponse,
  StrategyMode,
  TaskStatus,
  UserSessionListResponse,
  MonthlyReportResponse,
  HistoryImportRowPreview,
  HistoryImportPreviewResponse,
  HistoryImportConfirmResponse,
  TaskRunLogListResponse,
  AutomationTask,
  HealthResponse,
  TradingPreflightResponse,
  RetentionPolicy,
  RiskEvent,
  TeamMember,
  TenantInvitation,
  AiDailyReportResponse,
  PublicSignal,
  SharePerformance,
  InviteInfo,
} from '../types/api'

const BASE = '/api/v1'

let accessToken = ''

interface ApiErrorBody {
  message?: string
  detail?: string
  request_id?: string
}

async function request<T>(url: string, options: RequestInit = {}, retryOnAuth = true): Promise<T> {
  const isFormData = options.body instanceof FormData
  const method = (options.method || 'GET').toUpperCase()
  const headers: Record<string, string> = {
    ...(options.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...((options.headers as Record<string, string>) || {}),
  }

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = document.cookie
      .split('; ')
      .find((item) => item.startsWith('csrf_token='))
      ?.split('=')[1]
    if (csrf) headers['X-CSRF-Token'] = decodeURIComponent(csrf)
  }

  let response: Response
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include',
    })
  } catch (error) {
    throw new Error('后端服务未连接，请先启动 API 服务或稍后重试')
  }

  if (!response.ok) {
    if (response.status === 401 && retryOnAuth && !url.includes('/auth/refresh')) {
      const refreshed = await refreshAccessToken()
      if (refreshed) {
        return request<T>(url, options, false)
      }
    }
    const error = await response.json().catch((parseError: unknown): ApiErrorBody => {
      void parseError
      return { message: '请求失败' }
    })
    const requestId = error.request_id || response.headers.get('X-Request-ID') || ''
    const message = error.message || error.detail || `HTTP ${response.status}`
    const displayMessage = requestId ? `${message} · Request ID ${requestId}` : message
    window.dispatchEvent(new CustomEvent('kenne-toast', { detail: { message: displayMessage, tone: 'error' } }))
    throw new Error(displayMessage)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export function setTokens(access: string, _refresh: string) {
  accessToken = access
}

export function clearTokens() {
  accessToken = ''
}

export function isAuthenticated(): boolean {
  return Boolean(accessToken)
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const data = await request<TokenResponse>(`${BASE}/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  setTokens(data.access_token, data.refresh_token)
  return data
}

export async function register(email: string, password: string, displayName: string, acceptedTerms = false, referralCode = ''): Promise<TokenResponse> {
  const data = await request<TokenResponse>(`${BASE}/auth/register`, {
    method: 'POST',
    body: JSON.stringify({
      email,
      password,
      display_name: displayName,
      accepted_terms: acceptedTerms,
      referral_code: referralCode || undefined,
    }),
  })
  setTokens(data.access_token, data.refresh_token)
  return data
}

export async function acceptInvitation(token: string, password: string, displayName: string): Promise<TokenResponse> {
  const data = await request<TokenResponse>(`${BASE}/auth/invitations/accept`, {
    method: 'POST',
    body: JSON.stringify({ token, password, display_name: displayName }),
  })
  setTokens(data.access_token, data.refresh_token)
  return data
}

export async function refreshAccessToken(): Promise<boolean> {
  try {
    const data = await request<TokenResponse>(`${BASE}/auth/refresh`, {
      method: 'POST',
      body: JSON.stringify({}),
    }, false)
    setTokens(data.access_token, data.refresh_token)
    return true
  } catch (error) {
    void error
    clearTokens()
    return false
  }
}

export async function logout(): Promise<void> {
  await request(`${BASE}/auth/logout`, { method: 'POST' }).catch((error: unknown) => {
    void error
  })
  clearTokens()
}

export async function fetchMe(): Promise<UserInfo> {
  return request<UserInfo>(`${BASE}/auth/me`)
}

export async function fetchSignals(): Promise<Signal[]> {
  return request<Signal[]>(`${BASE}/signals`)
}

export async function fetchConfig(): Promise<UserConfig> {
  return request<UserConfig>(`${BASE}/config`)
}

export async function saveConfig(config: UserConfig): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/config`, {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function fetchExchanges(): Promise<Record<string, string>> {
  return request(`${BASE}/exchange/list`)
}

export async function fetchBalance(): Promise<Record<string, { free: number; used: number; total: number }>> {
  return request(`${BASE}/exchange/balance`)
}

export async function fetchTradingPreflight(): Promise<TradingPreflightResponse> {
  return request(`${BASE}/exchange/preflight`)
}

export async function runDca(dryRun: boolean, confirmLive = false): Promise<DcaRunResult> {
  const params = new URLSearchParams({
    dry_run: String(dryRun),
    confirm_live: String(confirmLive),
  })
  return request(`${BASE}/exchange/run-dca?${params.toString()}`, { method: 'POST' })
}

export async function updateMarketData(): Promise<{ symbol: string; added?: number; source?: string; error?: string }[]> {
  return request(`${BASE}/exchange/update-data`, { method: 'POST' })
}

export interface HistoryQuery {
  month?: string
  status?: string
  symbol?: string
  mode?: string
  start_date?: string
  end_date?: string
  page?: number
  page_size?: number
}

export async function fetchHistory(query: HistoryQuery = {}): Promise<HistoryResponse> {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== 'all') {
      params.set(key, String(value))
    }
  })
  const queryString = params.toString()
  return request(`${BASE}/history${queryString ? `?${queryString}` : ''}`)
}

export async function initHistory(): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/history/init`, { method: 'POST' })
}

export async function fetchHistoryStats(): Promise<HistoryStatsResponse> {
  return request(`${BASE}/history/stats`)
}

export async function fetchOperationAudit(query: {
  action?: string
  result?: string
  request_id?: string
  page?: number
  page_size?: number
} = {}): Promise<OperationAuditResponse> {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== 'all') params.set(key, String(value))
  })
  const queryString = params.toString()
  return request(`${BASE}/audit/operations${queryString ? `?${queryString}` : ''}`)
}

export function historyExportUrl(): string {
  return `${BASE}/history/export`
}

export function operationAuditExportUrl(): string {
  return `${BASE}/audit/operations/export`
}

export async function fetchMvrv(): Promise<{ ok: boolean; data: MvrvData[] }> {
  return request(`${BASE}/mvrv`)
}

export async function fetchPlans(): Promise<PlansResponse> {
  return request<PlansResponse>(`${BASE}/stripe/plans`)
}

export async function fetchBacktestStrategies(): Promise<StrategiesResponse> {
  return request<StrategiesResponse>(`${BASE}/backtest/strategies`)
}

export async function fetchLocalBacktestDatasets(): Promise<LocalDatasetsResponse> {
  return request<LocalDatasetsResponse>(`${BASE}/backtest/local-datasets`)
}

export async function createCheckout(plan: string): Promise<{ checkout_url: string }> {
  return request(`${BASE}/stripe/checkout?plan=${encodeURIComponent(plan)}`, { method: 'POST' })
}

export async function createBillingPortal(): Promise<{ portal_url: string }> {
  return request(`${BASE}/stripe/portal`, { method: 'POST' })
}

export async function devUpgradePlan(plan: string): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/stripe/dev-upgrade`, {
    method: 'POST',
    body: JSON.stringify({ plan }),
  })
}

export async function runCustomBacktest(payload: {
  strategy_mode: StrategyMode
  start_date: string
  end_date: string
  monthly_budget: number
  files?: File[]
  server_paths?: Partial<Record<'BTC' | 'ETH' | 'SOL', string>>
}): Promise<{ ok: boolean; data: BacktestResult }> {
  const form = new FormData()
  form.set('strategy_mode', payload.strategy_mode)
  form.set('start_date', payload.start_date)
  form.set('end_date', payload.end_date)
  form.set('monthly_budget', String(payload.monthly_budget))
  const files = payload.files || []
  files.forEach((file) => form.append('files', file))
  if (payload.server_paths) {
    const cleanPaths = Object.fromEntries(
      Object.entries(payload.server_paths).filter(([, value]) => Boolean(value?.trim())),
    )
    if (Object.keys(cleanPaths).length > 0) {
      form.set('server_paths', JSON.stringify(cleanPaths))
    }
  }
  return request(`${BASE}/backtest/custom`, {
    method: 'POST',
    body: form,
  })
}

export async function changePassword(payload: {
  current_password: string
  new_password: string
}): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/auth/change-password`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function forgotPassword(email: string): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/auth/forgot-password`, {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export async function resetPassword(token: string, newPassword: string): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/auth/reset-password`, {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword }),
  })
}

export async function verifyEmail(token: string): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/auth/verify-email`, {
    method: 'POST',
    body: JSON.stringify({ token }),
  })
}

export async function resendVerificationEmail(): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/auth/resend-verification`, { method: 'POST' })
}

export async function testEmail(payload: { subject?: string; message?: string } = {}): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/notifications/test-email`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchTaskStatus(): Promise<TaskStatus> {
  return request(`${BASE}/tasks/status`)
}

export async function fetchTaskRuns(page = 1): Promise<TaskRunLogListResponse> {
  return request(`${BASE}/tasks/runs?page=${page}&page_size=25`)
}

export async function updateTask(taskId: number, payload: { enabled?: boolean; interval_minutes?: number }): Promise<{ ok: boolean; task: AutomationTask }> {
  return request(`${BASE}/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function runAutomationNow(): Promise<{ ok: boolean; processed: number; message: string }> {
  return request(`${BASE}/tasks/run-now`, {
    method: 'POST',
    body: JSON.stringify({ task: 'automation_dry_run', dry_run: true }),
  })
}

export async function fetchSessions(): Promise<UserSessionListResponse> {
  return request(`${BASE}/security/sessions`)
}

export async function revokeSession(sessionId: string): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/security/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
}

export async function previewHistoryImport(file: File): Promise<HistoryImportPreviewResponse> {
  const form = new FormData()
  form.set('file', file)
  return request(`${BASE}/history/import/preview`, {
    method: 'POST',
    body: form,
  })
}

export async function confirmHistoryImport(file: File): Promise<HistoryImportConfirmResponse> {
  const form = new FormData()
  form.set('file', file)
  return request(`${BASE}/history/import/confirm`, {
    method: 'POST',
    body: form,
  })
}

export async function fetchMonthlyReport(): Promise<MonthlyReportResponse> {
  return request(`${BASE}/reports/monthly`)
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request(`${BASE}/health`)
}

export async function fetchHealthDetail(): Promise<HealthResponse> {
  return request(`${BASE}/health/detail`)
}

export async function fetchTeamMembers(): Promise<{ users: TeamMember[] }> {
  return request(`${BASE}/admin/users`)
}

export async function fetchInvitations(): Promise<{ invitations: TenantInvitation[] }> {
  return request(`${BASE}/admin/invitations`)
}

export async function createInvitation(email: string, role: string): Promise<{ ok: boolean; invitation: TenantInvitation }> {
  return request(`${BASE}/admin/invitations`, {
    method: 'POST',
    body: JSON.stringify({ email, role }),
  })
}

export async function revokeInvitation(id: number): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/admin/invitations/${id}`, { method: 'DELETE' })
}

export async function updateUserRole(userId: number, role: string, stepUpCode = ''): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/admin/users/${userId}/role`, {
    method: 'PATCH',
    headers: stepUpCode ? { 'X-Step-Up-Code': stepUpCode } : {},
    body: JSON.stringify({ role }),
  })
}

export async function requestAccountDeletion(): Promise<{ ok: boolean; message: string; token?: string }> {
  return request(`${BASE}/security/deletion/request`, { method: 'POST' })
}

export async function confirmAccountDeletion(token: string, stepUpCode = ''): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/security/deletion/confirm`, {
    method: 'POST',
    headers: stepUpCode ? { 'X-Step-Up-Code': stepUpCode } : {},
    body: JSON.stringify({ token }),
  })
}

export async function setupMfa(): Promise<{ ok: boolean; secret: string; otpauth_url: string }> {
  return request(`${BASE}/security/mfa/setup`, { method: 'POST' })
}

export async function enableMfa(secret: string, code: string): Promise<{ ok: boolean; message: string; backup_codes: string[] }> {
  return request(`${BASE}/security/mfa/enable`, {
    method: 'POST',
    body: JSON.stringify({ secret, code }),
  })
}

export async function disableMfa(stepUpCode = ''): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/security/mfa/disable`, {
    method: 'POST',
    headers: stepUpCode ? { 'X-Step-Up-Code': stepUpCode } : {},
  })
}

export async function fetchRiskEvents(): Promise<{ events: RiskEvent[] }> {
  return request(`${BASE}/admin/risk-events`)
}

export async function resolveRiskEvent(id: number): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/admin/risk-events/${id}/resolve`, { method: 'POST' })
}

export async function fetchRetentionPolicy(): Promise<RetentionPolicy> {
  return request(`${BASE}/admin/retention-policy`)
}

export async function saveRetentionPolicy(policy: RetentionPolicy): Promise<{ ok: boolean; message: string }> {
  return request(`${BASE}/admin/retention-policy`, {
    method: 'POST',
    body: JSON.stringify(policy),
  })
}

export async function runRetentionCleanup(): Promise<{ ok: boolean; deleted: Record<string, number> }> {
  return request(`${BASE}/admin/retention/cleanup`, { method: 'POST' })
}

export async function fetchAiDailyReport(): Promise<AiDailyReportResponse> {
  return request<AiDailyReportResponse>(`${BASE}/reports/ai-daily`)
}

export async function fetchPublicSignals(): Promise<PublicSignal[]> {
  return request<PublicSignal[]>(`${BASE}/signals/public`)
}

export async function fetchSharePerformance(): Promise<SharePerformance> {
  return request<SharePerformance>(`${BASE}/share/performance`)
}

export async function fetchInviteInfo(code: string): Promise<InviteInfo> {
  return request<InviteInfo>(`${BASE}/share/invite-info?code=${encodeURIComponent(code)}`)
}
