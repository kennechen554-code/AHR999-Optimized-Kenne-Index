export type StrategyMode = 'per_asset_strict_dd' | 'per_asset_balanced_return'

export interface Signal {
  symbol: string
  price: number
  cost_200: number
  valuation: number
  kenne_index: number
  zone: string
  momentum: string
  ret_7d: number
  ret_14d: number
  base_mult: number
  final_mult: number
  score: number
  pct_rank: number
  pct: Record<string, number>
  slope: number
  r2: number
  data_years: number
  date: string
  error?: string | null
}

export interface UserConfig {
  exchange: string
  api_key: string
  api_secret: string
  api_passphrase: string
  simulated: boolean
  budget_mode: string
  budget_amount: number
  run_interval_days: number
  strategy_mode: StrategyMode
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_password: string
  email_to: string
  notifications_enabled: boolean
  notify_on_execution: boolean
  notify_on_budget: boolean
  notify_on_error: boolean
  automation_enabled: boolean
  automation_market_data: boolean
  automation_dry_run: boolean
  automation_live_enabled: boolean
}

export interface TradeRecord {
  id: number
  ts: string
  symbol: string
  exchange: string
  mode: string
  strategy_mode: StrategyMode
  usdt: number
  kenne_index: number
  mult: number
  momentum: string
  order_id: string
  status: string
  note: string
  price: number
  qty: number
  created_at: string
}

export interface HistoryResponse {
  records: TradeRecord[]
  total: number
  count: number
  page: number
  page_size: number
}

export interface AssetHistoryStat {
  symbol: string
  total_usdt: number
  total_qty: number
  avg_price: number
  sim_usdt: number
  live_usdt: number
}

export interface HistoryStatsResponse {
  assets: AssetHistoryStat[]
  total_usdt: number
  total_qty: number
}

export interface DcaRunResult {
  ok: boolean
  mode: string
  total_usdt: number
  orders: Record<string, unknown>[]
  message: string
}

export interface HealthResponse {
  app: string
  database: string
  redis: string
  system_smtp: boolean
  stripe_webhook: boolean
  tasks: {
    running: boolean
    last_started_at: string
    last_finished_at: string
    last_message: string
    last_error: string
  }
  market_data: Record<string, {
    exists: boolean
    updated_at: number | null
    size_bytes: number
  }>
}

export interface TradingPreflightCheck {
  key: string
  ok: boolean
  message: string
}

export interface TradingPreflightResponse {
  ok: boolean
  exchange: string
  simulated: boolean
  budget: {
    mode: string
    monthly_budget: number
    spent_live: number
    spent_dry: number
    remaining_live: number
  }
  live: {
    enabled_by_plan: boolean
    global_enabled: boolean
    tenant_paused: boolean
    cap_usdt: number
  }
  balance: {
    status: string
    error: string
  }
  market_data: Record<string, {
    exists: boolean
    updated_at: string
    age_hours: number | null
    size_bytes: number
  }>
  checks: TradingPreflightCheck[]
}

export interface MvrvData {
  symbol: string
  mvrv_z: number
  market_cap: number
  realized_cap: number
  realized_price?: number
  current_price?: number
  rank: number
  vol_24h: number
  supply: number
  funding: Record<string, number> | null
  depth: Record<string, number> | null
  source?: string
  model?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface TenantInfo {
  id: number
  name: string
  max_users: number
}

export interface Entitlements {
  signals: boolean
  mvrv: boolean
  simulated_trading: boolean
  live_trading: boolean
  backtesting: boolean
  automation: boolean
  email_reports: boolean
  ai_daily_report: boolean
  max_exchanges: number
  max_live_order_usdt: number
  supported_exchanges: string[]
}

export interface UserInfo {
  id: number
  email: string
  display_name: string
  role: string
  tenant_id: number
  plan: 'free' | 'basic' | 'premium'
  tenant: TenantInfo
  subscription_status: string
  entitlements: Entitlements
  email_verified: boolean
  mfa_enabled: boolean
  referral_code?: string | null
}

export interface TeamMember {
  id: number
  email: string
  display_name: string
  role: 'owner' | 'admin' | 'member'
  is_active: boolean
  email_verified: boolean
  created_at: string
}

export interface TenantInvitation {
  id: number
  email: string
  role: 'owner' | 'admin' | 'member'
  expires_at: string
  accepted_at: string
  revoked_at: string
  token?: string
}

export interface RiskEvent {
  id: number
  event_type: string
  severity: string
  summary: string
  request_id: string
  created_at: string
  resolved_at: string
}

export interface RetentionPolicy {
  operation_audit_days: number
  task_run_days: number
  risk_event_days: number
}

export interface PlanInfo {
  id: 'basic' | 'premium'
  name: string
  name_en: string
  price: string
  period: string
  description: string
  features: string[]
  entitlements: Partial<Entitlements>
  recommended?: boolean
}

export interface PlansResponse {
  plans: PlanInfo[]
}

export interface BacktestSeriesPoint {
  date: string
  equity: number
  nav: number
  drawdown: number
}

export interface BacktestResult {
  strategy_mode: StrategyMode
  strategy_label: string
  start: string
  end: string
  final_equity: number
  total_contrib: number
  profit: number
  total_return: number
  xirr: number
  max_drawdown: number
  avg_utilization: number
  spent_ratio: number
  cash_end: number
  trades: number
  deploy_weights: Record<string, number>
  series: BacktestSeriesPoint[]
}

export interface StrategyAssetMetadata {
  symbol: string
  interval_days: number
  budget_weight: number
  deep_threshold: number
  dca_threshold: number
  stop_threshold: number
  falling_multiplier: number
  stabilizing_multiplier: number
}

export interface StrategyMetadata {
  mode: StrategyMode
  label: string
  default: boolean
  risk_level: string
  description: string
  reserve_frac: number
  reserve_release_score: number
  assets: StrategyAssetMetadata[]
}

export interface StrategiesResponse {
  default: StrategyMode
  strategies: StrategyMetadata[]
}

export interface LocalDataset {
  symbol: string
  path: string
  exists: boolean
  updated_at: number | null
  size_bytes: number
}

export interface LocalDatasetsResponse {
  allowed_dirs: string[]
  datasets: LocalDataset[]
}

export interface OperationAuditLog {
  id: number
  user_id: number
  tenant_id: number
  action: string
  resource_type: string
  resource_id: string
  request_id: string
  result: string
  summary: string
  ip_address: string
  user_agent: string
  created_at: string
}

export interface OperationAuditResponse {
  records: OperationAuditLog[]
  count: number
  page: number
  page_size: number
}

export interface TaskStatus {
  running: boolean
  last_started_at: string
  last_finished_at: string
  last_message: string
  last_error: string
  tasks: AutomationTask[]
  recent_runs: TaskRunLog[]
}

export interface UserSessionInfo {
  id: number
  session_id: string
  ip_address: string
  user_agent: string
  is_current: boolean
  created_at: string
  last_seen_at: string
}

export interface UserSessionListResponse {
  sessions: UserSessionInfo[]
}

export interface AutomationTask {
  id: number
  task_type: 'market_data' | 'automation_dry_run' | 'automation_live'
  enabled: boolean
  interval_minutes: number
  next_run_at: string
  last_run_at: string
  last_result: string
  last_message: string
  consecutive_failures: number
}

export interface TaskRunLog {
  id: number
  task_type: string
  status: string
  message: string
  started_at: string
  finished_at: string
}

export interface TaskRunLogListResponse {
  records: TaskRunLog[]
  count: number
  page: number
  page_size: number
}

export interface HistoryImportRowPreview {
  row_number: number
  symbol: string
  status: string
  mode: string
  usdt: number
  dedupe_key: string
  error: string
  duplicate: boolean
}

export interface HistoryImportPreviewResponse {
  ok: boolean
  valid_count: number
  invalid_count: number
  duplicate_count: number
  rows: HistoryImportRowPreview[]
  message: string
}

export interface HistoryImportConfirmResponse {
  ok: boolean
  imported_count: number
  skipped_duplicates: number
  message: string
}

export interface MonthlyReportItem {
  month: string
  total_usdt: number
  total_qty: number
  sim_usdt: number
  live_usdt: number
  trade_count: number
  estimated_value: number
  estimated_pnl: number
}

export interface MonthlyReportResponse {
  disclaimer: string
  months: MonthlyReportItem[]
}

export interface AiDailyReportResponse {
  content: string
  generated_at: string
}

export interface HistoricalSignalPoint {
  date: string
  price: number
  kenne_index: number
  valuation: number
  cost_200: number
}

export interface PublicSignal {
  symbol: string
  price: number
  cost_200: number
  valuation: number
  kenne_index: number
  zone: string
  momentum: string
  ret_7d: number
  ret_14d: number
  base_mult: number
  final_mult: number
  score: number
  pct_rank: number
  pct: Record<string, number>
  slope: number
  r2: number
  data_years: number
  date: string
  history: HistoricalSignalPoint[]
  error: string | null
}

export interface AssetPerformance {
  symbol: string
  cost: number
  qty: number
  current_price: number
  value: number
  profit: number
  profit_rate: number
}

export interface SharePerformance {
  referral_code: string
  invited_count: number
  total_invested: number
  current_value: number
  total_profit: number
  profit_rate: number
  assets: AssetPerformance[]
}

export interface InviteInfo {
  referrer_name: string
  profit_rate: number
  invited_count: number
}
