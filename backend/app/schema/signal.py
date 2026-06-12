"""
Pydantic 模型 — 信号、配置、交易、通用响应。
"""

from pydantic import BaseModel, ConfigDict, Field


# ─── 通用 ─────────────────────────────────────────────────────────

class ApiResponse(BaseModel):
    """统一 API 响应包装。"""
    ok: bool = True
    message: str = ""


# ─── 信号 ─────────────────────────────────────────────────────────

class SignalResponse(BaseModel):
    """Kenne Index 信号响应。"""
    symbol: str
    price: float = 0.0
    cost_200: float = 0.0
    valuation: float = 0.0
    kenne_index: float = 0.0
    zone: str = ""
    momentum: str = ""
    ret_7d: float = 0.0
    ret_14d: float = 0.0
    base_mult: float = 0.0
    final_mult: float = 0.0
    score: int = 0
    pct_rank: float = 0.0
    pct: dict[str, float] = {}
    slope: float = 0.0
    r2: float = 0.0
    data_years: float = 0.0
    date: str = ""
    error: str | None = None


# ─── 配置 ─────────────────────────────────────────────────────────

class ConfigUpdateRequest(BaseModel):
    """用户配置更新请求。"""
    model_config = ConfigDict(extra="forbid")

    exchange: str = "okx"
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    simulated: bool = True
    budget_mode: str = "MONTHLY"
    budget_amount: float = Field(default=700.0, gt=0, le=1_000_000)
    run_interval_days: int = Field(default=7, ge=1, le=30)
    strategy_mode: str = "per_asset_strict_dd"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""
    notifications_enabled: bool = False
    notify_on_execution: bool = True
    notify_on_budget: bool = True
    notify_on_error: bool = True
    automation_enabled: bool = False
    automation_market_data: bool = False
    automation_dry_run: bool = False
    automation_live_enabled: bool = False


class ConfigResponse(BaseModel):
    """用户配置响应（敏感信息已掩码）。"""
    exchange: str = "okx"
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    simulated: bool = True
    budget_mode: str = "MONTHLY"
    budget_amount: float = 700.0
    run_interval_days: int = 7
    strategy_mode: str = "per_asset_strict_dd"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_to: str = ""
    notifications_enabled: bool = False
    notify_on_execution: bool = True
    notify_on_budget: bool = True
    notify_on_error: bool = True
    automation_enabled: bool = False
    automation_market_data: bool = False
    automation_dry_run: bool = False
    automation_live_enabled: bool = False


# ─── 交易记录 ─────────────────────────────────────────────────────

class TradeRecordResponse(BaseModel):
    """交易记录响应。"""
    id: int
    ts: str
    symbol: str
    exchange: str
    mode: str = "dry_run"
    strategy_mode: str = "per_asset_strict_dd"
    usdt: float
    kenne_index: float
    mult: float
    momentum: str
    order_id: str
    status: str
    note: str
    price: float
    qty: float
    created_at: str = ""


class TradeRecordCreateRequest(BaseModel):
    """开发环境内部调试写入审计记录请求。"""
    model_config = ConfigDict(extra="forbid")

    ts: str = ""
    symbol: str
    exchange: str = "okx"
    mode: str = "dry_run"
    strategy_mode: str = "per_asset_strict_dd"
    usdt: float = 0.0
    kenne_index: float = 0.0
    mult: float = 0.0
    momentum: str = ""
    order_id: str = ""
    status: str = "dry_run"
    note: str = ""
    price: float = 0.0
    qty: float = 0.0


class HistoryResponse(BaseModel):
    """历史记录列表响应。"""
    records: list[TradeRecordResponse]
    total: float
    count: int
    page: int = 1
    page_size: int = 25


class AssetHistoryStat(BaseModel):
    """资产维度审计统计。"""
    symbol: str
    total_usdt: float = 0.0
    total_qty: float = 0.0
    avg_price: float = 0.0
    sim_usdt: float = 0.0
    live_usdt: float = 0.0


class HistoryStatsResponse(BaseModel):
    """交易审计统计响应。"""
    assets: list[AssetHistoryStat]
    total_usdt: float = 0.0
    total_qty: float = 0.0


# ─── 分配 ─────────────────────────────────────────────────────────

class AllocationItem(BaseModel):
    """资金分配项。"""
    symbol: str
    usdt_amount: float
    weight: float
    kenne_index: float
    final_mult: float
    zone: str


# ─── DCA 执行结果 ─────────────────────────────────────────────────

class DcaRunResponse(BaseModel):
    """定投执行结果。"""
    ok: bool
    mode: str = ""
    total_usdt: float = 0.0
    orders: list[dict] = []
    message: str = ""
