"""
Prometheus 监控自定义业务指标。
"""

from prometheus_client import Counter

# 1. 定投任务执行次数计数器
# 维度: symbol (币种), status (filled/failed/dry_run), mode (live/dry_run)
DCA_EXECUTIONS = Counter(
    "dca_executions_total",
    "Total number of DCA executions",
    ["symbol", "status", "mode"]
)

# 2. 定投扣款总金额计数器 (USDT)
# 维度: symbol (币种), mode (live/dry_run)
DCA_AMOUNT = Counter(
    "dca_amount_total",
    "Total amount allocated to DCA purchases in USDT",
    ["symbol", "mode"]
)

# 3. 交易所 API 调用错误计数器
# 维度: exchange (交易所名称，如 okx), operation (操作名称，如 fetch_balance / create_market_buy_order)
EXCHANGE_API_ERRORS = Counter(
    "exchange_api_errors_total",
    "Total number of errors returned by Exchange APIs",
    ["exchange", "operation"]
)

# 4. 自动化任务运行失败计数器
# 维度: task_id (任务所属的 tenant_id_task_id 或 task_id 标识), task_type (任务类型，如 automation_live)
TASK_FAILURES = Counter(
    "task_failures_total",
    "Total number of automated task failures",
    ["task_id", "task_type"]
)
