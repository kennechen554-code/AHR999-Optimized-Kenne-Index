"""操作审计与任务/通知相关 schema。"""

from pydantic import BaseModel, ConfigDict


class OperationAuditLogResponse(BaseModel):
    id: int
    user_id: int
    tenant_id: int
    action: str
    resource_type: str = ""
    resource_id: str = ""
    request_id: str = ""
    result: str = "success"
    summary: str = ""
    ip_address: str = ""
    user_agent: str = ""
    created_at: str


class OperationAuditListResponse(BaseModel):
    records: list[OperationAuditLogResponse]
    count: int
    page: int = 1
    page_size: int = 25


class UserSessionResponse(BaseModel):
    id: int
    session_id: str
    ip_address: str = ""
    user_agent: str = ""
    is_current: bool = False
    created_at: str = ""
    last_seen_at: str = ""


class UserSessionListResponse(BaseModel):
    sessions: list[UserSessionResponse]


class AutomationTaskResponse(BaseModel):
    id: int
    task_type: str
    enabled: bool
    interval_minutes: int
    next_run_at: str = ""
    last_run_at: str = ""
    last_result: str = ""
    last_message: str = ""
    consecutive_failures: int = 0


class AutomationTaskUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    interval_minutes: int | None = None


class TaskRunLogResponse(BaseModel):
    id: int
    task_type: str
    status: str
    message: str = ""
    started_at: str = ""
    finished_at: str = ""


class TaskRunLogListResponse(BaseModel):
    records: list[TaskRunLogResponse]
    count: int
    page: int = 1
    page_size: int = 25


class TestEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = "Kenne Index 测试邮件"
    message: str = "这是一封来自 Kenne Index 的测试邮件。"


class TaskRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = "market_data"
    dry_run: bool = True


class TaskStatusResponse(BaseModel):
    running: bool
    last_started_at: str = ""
    last_finished_at: str = ""
    last_message: str = ""
    last_error: str = ""
    tasks: list[AutomationTaskResponse] = []
    recent_runs: list[TaskRunLogResponse] = []


class HistoryImportRowPreview(BaseModel):
    row_number: int
    symbol: str = ""
    status: str = ""
    mode: str = ""
    usdt: float = 0.0
    dedupe_key: str = ""
    error: str = ""
    duplicate: bool = False


class HistoryImportPreviewResponse(BaseModel):
    ok: bool = True
    valid_count: int = 0
    invalid_count: int = 0
    duplicate_count: int = 0
    rows: list[HistoryImportRowPreview] = []
    message: str = ""


class HistoryImportConfirmResponse(BaseModel):
    ok: bool = True
    imported_count: int = 0
    skipped_duplicates: int = 0
    message: str = ""


class MonthlyReportItem(BaseModel):
    month: str
    total_usdt: float = 0.0
    total_qty: float = 0.0
    sim_usdt: float = 0.0
    live_usdt: float = 0.0
    trade_count: int = 0
    estimated_value: float = 0.0
    estimated_pnl: float = 0.0


class MonthlyReportResponse(BaseModel):
    disclaimer: str
    months: list[MonthlyReportItem]


class AiDailyReportResponse(BaseModel):
    content: str
    generated_at: str
