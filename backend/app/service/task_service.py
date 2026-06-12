"""Lightweight in-process task runner for local SaaS automation."""

from datetime import datetime, timedelta, timezone
import asyncio
import hashlib
import hmac
import json
import logging

import httpx

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_main_session_factory
from app.core.redis_client import get_redis
from app.model.tenant_models import AutomationTask, TaskRunLog, UserConfig, TradeRecord
from app.repository.history_repository import add_trade_records, monthly_spent
from app.service.dca_service import run_dca

logger = logging.getLogger(__name__)

DEFAULT_TASKS: dict[str, int] = {
    "market_data": 240,
    "automation_dry_run": 1440,
    "automation_live": 1440,
    "reconciliation": 1440,
}
SCHEDULER_TICK_LOCK_KEY = "kenne:scheduler:due-tasks"
SCHEDULER_TICK_LOCK_TTL_SECONDS = 75


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def ensure_user_tasks(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
) -> list[AutomationTask]:
    rows = await session.execute(
        select(AutomationTask).where(
            AutomationTask.user_id == user_id,
            AutomationTask.tenant_id == tenant_id,
        )
    )
    existing = {item.task_type: item for item in rows.scalars().all()}
    for task_type, interval in DEFAULT_TASKS.items():
        if task_type not in existing:
            task = AutomationTask(
                user_id=user_id,
                tenant_id=tenant_id,
                task_type=task_type,
                interval_minutes=interval,
                next_run_at=_now() + timedelta(minutes=interval),
            )
            session.add(task)
            existing[task_type] = task
    await session.flush()
    return [existing[key] for key in DEFAULT_TASKS]


def task_to_dict(task: AutomationTask) -> dict[str, object]:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "enabled": task.enabled,
        "interval_minutes": task.interval_minutes,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else "",
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else "",
        "last_result": task.last_result,
        "last_message": task.last_message,
        "consecutive_failures": task.consecutive_failures,
    }


def run_log_to_dict(log: TaskRunLog) -> dict[str, object]:
    return {
        "id": log.id,
        "task_type": log.task_type,
        "status": log.status,
        "message": log.message,
        "started_at": log.started_at.isoformat() if log.started_at else "",
        "finished_at": log.finished_at.isoformat() if log.finished_at else "",
    }


async def list_task_runs(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, object]], int, int]:
    from sqlalchemy import func

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = [TaskRunLog.user_id == user_id, TaskRunLog.tenant_id == tenant_id]
    count_result = await session.execute(select(func.count()).select_from(TaskRunLog).where(*filters))
    count = int(count_result.scalar_one() or 0)
    rows = await session.execute(
        select(TaskRunLog)
        .where(*filters)
        .order_by(TaskRunLog.started_at.desc(), TaskRunLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [run_log_to_dict(item) for item in rows.scalars().all()], count, page_size


async def record_task_run(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
    task_type: str,
    status: str,
    message: str,
    started_at: datetime | None = None,
) -> TaskRunLog:
    finished_at = _now()
    log = TaskRunLog(
        user_id=user_id,
        tenant_id=tenant_id,
        task_type=task_type,
        status=status,
        message=message[:512],
        started_at=started_at or finished_at,
        finished_at=finished_at,
    )
    session.add(log)
    if status == "failed":
        from app.core.metrics import TASK_FAILURES
        TASK_FAILURES.labels(task_id=f"{tenant_id}_{task_type}", task_type=task_type).inc()
        
    task_rows = await session.execute(
        select(AutomationTask).where(
            AutomationTask.user_id == user_id,
            AutomationTask.tenant_id == tenant_id,
            AutomationTask.task_type == task_type,
        )
    )
    task = task_rows.scalar_one_or_none()
    if task:
        task.last_run_at = log.finished_at
        task.last_result = status
        task.last_message = message[:512]
        task.consecutive_failures = 0 if status in {"success", "skipped"} else task.consecutive_failures + 1
        task.next_run_at = finished_at + timedelta(minutes=max(task.interval_minutes, 5))
        if task.consecutive_failures >= 3:
            task.enabled = False
            from app.service.alert_service import send_alert
            asyncio.create_task(
                send_alert(
                    title=f"自动化任务已熔断禁用: {task_type}",
                    message=(
                        f"用户 ID: {user_id}\n"
                        f"租户 ID: {tenant_id}\n"
                        f"任务类型: {task_type}\n"
                        f"连续失败次数: {task.consecutive_failures}\n"
                        f"最后错误消息: {message}"
                    ),
                    severity="critical"
                )
            )
    await session.flush()
    return log


async def _notify_hermes_async(task_type: str, status: str, message: str) -> None:
    """Fire-and-forget 通知 Hermes Agent。失败静默，不影响主流程。"""
    settings = get_settings()
    url = settings.hermes_webhook_url
    secret = settings.hermes_webhook_secret
    if not url:
        return
    try:
        payload = json.dumps({
            "event": {
                "type": "automation_task",
                "action": task_type,
                "data": {"status": status, "message": message}
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                url,
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={sig}"
                }
            )
    except Exception as e:
        logger.warning("Hermes webhook notify failed: %s", e)


async def _run_dry_run_for_config(
    session: AsyncSession,
    cfg: UserConfig,
    started_at: datetime,
) -> tuple[str, str]:
    settings = get_settings()
    spent = await monthly_spent(session, cfg.user_id, cfg.tenant_id, statuses=("dry_run",))
    remaining = max(float(cfg.budget_amount or 0) - spent, 0)
    if remaining <= 0:
        return "skipped", "月度预算已用完"

    payload = {
        "exchange": cfg.exchange,
        "api_key_encrypted": cfg.api_key_encrypted,
        "api_secret_encrypted": cfg.api_secret_encrypted,
        "api_passphrase_encrypted": cfg.api_passphrase_encrypted,
        "simulated": cfg.simulated,
        "budget_mode": cfg.budget_mode,
        "budget_amount": min(float(cfg.budget_amount or 0), remaining),
        "run_interval_days": cfg.run_interval_days,
        "strategy_mode": cfg.strategy_mode,
    }
    result = await run_dca(payload, settings.data_files, dry_run=True)
    await add_trade_records(
        session,
        user_id=cfg.user_id,
        tenant_id=cfg.tenant_id,
        orders=result.get("orders", []),
        mode=str(result.get("mode") or "dry_run"),
        strategy_mode=cfg.strategy_mode,
    )
    return ("success" if result.get("ok") else "failed"), str(result.get("message", ""))


async def resolve_pending_orders(session_factory=None) -> None:
    """
    回溯系统崩溃或网络超时遗留的 'pending' 状态交易记录。
    
    检测交易所历史成交并恢复状态机。
    """
    from app.service.exchange_service import create_exchange
    from app.service.alert_service import send_alert
    
    logger.info("Starting pending trade records resolution...")
    factory = session_factory or get_main_session_factory()
    try:
        async with factory() as session:
            # 查询 pending 交易
            rows = await session.execute(
                select(TradeRecord).where(TradeRecord.order_status == "pending")
            )
            pending_records = rows.scalars().all()
            if not pending_records:
                logger.info("No pending trade records found")
                return
                
            logger.info("Found %d pending trade records to resolve", len(pending_records))
            for record in pending_records:
                try:
                    # 获取配置
                    cfg_result = await session.execute(
                        select(UserConfig).where(
                            UserConfig.user_id == record.user_id,
                            UserConfig.tenant_id == record.tenant_id,
                        )
                    )
                    cfg = cfg_result.scalar_one_or_none()
                    if not cfg or not cfg.api_key_encrypted:
                        logger.warning("No exchange config found for user %d, skipping pending resolve", record.user_id)
                        continue
                    
                    # 创建 ccxt 交易所连接
                    exchange = create_exchange(
                        cfg.exchange,
                        cfg.api_key_encrypted,
                        cfg.api_secret_encrypted,
                        cfg.api_passphrase_encrypted,
                        cfg.simulated,
                    )
                    
                    # 拉取最近的成交， since_ms 传入创建时间前 5 分钟
                    created_at_utc = record.created_at if record.created_at.tzinfo else record.created_at.replace(tzinfo=timezone.utc)
                    since_ms = int(created_at_utc.timestamp() * 1000) - 300000
                    symbol_pair = f"{record.symbol}/USDT"
                    
                    trades = []
                    try:
                        trades = await exchange.fetch_my_trades(symbol_pair, since=since_ms)
                    except Exception as e:
                        logger.warning("Failed to fetch trades for %s: %s", symbol_pair, e)
                    finally:
                        await exchange.close()
                    
                    # 在 trades 中匹配接近金额的成交
                    matched_trade = None
                    for t in trades:
                        # 匹配时间偏差在 5 分钟 (300,000 ms) 内，且 cost 与 record.usdt 误差在 1% 内
                        time_diff = abs(t["timestamp"] - int(created_at_utc.timestamp() * 1000))
                        cost_diff = abs(t["cost"] - record.usdt) / (record.usdt or 1.0)
                        if time_diff <= 300000 and cost_diff <= 0.01:
                            matched_trade = t
                            break
                    
                    now = datetime.now(timezone.utc).replace(tzinfo=None)
                    age_minutes = (now - record.created_at.replace(tzinfo=None)).total_seconds() / 60.0
                    
                    if matched_trade:
                        # 匹配成功，更新状态机
                        record.status = "filled"
                        record.order_status = "filled"
                        record.price = float(matched_trade.get("price") or 0)
                        record.qty = float(matched_trade.get("amount") or 0)
                        record.order_id = str(matched_trade.get("order") or matched_trade.get("id") or "")
                        record.note = f"Pending resolved: matched trade ID {matched_trade.get('id')}"
                        await session.commit()
                        
                        await send_alert(
                            title=f"未决订单已成功回溯找回: {record.symbol}",
                            message=(
                                f"用户 ID: {record.user_id}\n"
                                f"租户 ID: {record.tenant_id}\n"
                                f"资产: {record.symbol}\n"
                                f"金额: {record.usdt} USDT\n"
                                f"实际成交价: {record.price}\n"
                                f"数量: {record.qty}\n"
                                f"交易 ID: {matched_trade.get('id')}"
                            ),
                            severity="info"
                        )
                    elif age_minutes > 10.0:
                        # 超过 10 分钟未能匹配，设为失败
                        record.status = "failed"
                        record.order_status = "failed"
                        record.note = "Pending resolved: confirmed not executed (timeout > 10m)"
                        await session.commit()
                        
                        await send_alert(
                            title=f"未决订单确认未成交，已重置: {record.symbol}",
                            message=(
                                f"用户 ID: {record.user_id}\n"
                                f"租户 ID: {record.tenant_id}\n"
                                f"资产: {record.symbol}\n"
                                f"金额: {record.usdt} USDT\n"
                                f"说明: 超时 10 分钟未能在交易所匹配到成交，已安全重置为失败。"
                            ),
                            severity="warning"
                        )
                except Exception as err:
                    logger.exception("Error resolving pending record id=%d: %s", record.id, err)
    except Exception as err:
        logger.error("Failed to run resolve_pending_orders scheduler: %s", err)


class TaskRuntime:
    def __init__(self) -> None:
        self.running = False
        self.last_started_at = ""
        self.last_finished_at = ""
        self.last_message = ""
        self.last_error = ""
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    def status(self) -> dict[str, str | bool]:
        return {
            "running": self.running,
            "last_started_at": self.last_started_at,
            "last_finished_at": self.last_finished_at,
            "last_message": self.last_message,
            "last_error": self.last_error,
        }

    async def status_for_user(
        self,
        session: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> dict[str, object]:
        tasks = await ensure_user_tasks(session, user_id, tenant_id)
        rows = await session.execute(
            select(TaskRunLog)
            .where(TaskRunLog.user_id == user_id, TaskRunLog.tenant_id == tenant_id)
            .order_by(TaskRunLog.started_at.desc(), TaskRunLog.id.desc())
            .limit(5)
        )
        return {
            **self.status(),
            "tasks": [task_to_dict(task) for task in tasks],
            "recent_runs": [run_log_to_dict(item) for item in rows.scalars().all()],
        }

    async def _run_due_task(
        self,
        session: AsyncSession,
        task: AutomationTask,
        started_at: datetime,
    ) -> bool:
        if task.task_type == "automation_dry_run":
            cfg_result = await session.execute(
                select(UserConfig).where(
                    UserConfig.user_id == task.user_id,
                    UserConfig.tenant_id == task.tenant_id,
                )
            )
            cfg = cfg_result.scalar_one_or_none()
            if not cfg or not cfg.automation_enabled or not cfg.automation_dry_run:
                await record_task_run(
                    session,
                    task.user_id,
                    task.tenant_id,
                    task.task_type,
                    "skipped",
                    "自动 dry-run 未在配置中启用",
                    started_at=started_at,
                )
                return False
            status, message = await _run_dry_run_for_config(session, cfg, started_at)
            await record_task_run(
                session,
                task.user_id,
                task.tenant_id,
                task.task_type,
                status,
                message,
                started_at=started_at,
            )
            # Hermes webhook 通知（fire-and-forget，不影响主流程）
            asyncio.create_task(_notify_hermes_async(task.task_type, status, message))
            return status == "success"

        if task.task_type == "reconciliation":
            from app.service.reconciliation_service import reconcile_balances
            await reconcile_balances(session, task.user_id, task.tenant_id)
            await record_task_run(
                session,
                task.user_id,
                task.tenant_id,
                task.task_type,
                "success",
                "每日资产对账完成",
                started_at=started_at,
            )
            return True

        if task.task_type == "market_data":
            await record_task_run(
                session,
                task.user_id,
                task.tenant_id,
                task.task_type,
                "skipped",
                "行情刷新需通过受控接口手动触发，自动任务仅记录调度心跳",
                started_at=started_at,
            )
            return False

        await record_task_run(
            session,
            task.user_id,
            task.tenant_id,
            task.task_type,
            "skipped",
            "自动实盘默认关闭，需后续风控确认后启用",
            started_at=started_at,
        )
        return False

    async def _acquire_scheduler_tick_lock(self) -> bool:
        client = await get_redis()
        if client is None:
            logger.info("scheduler tick lock skipped because Redis is unavailable")
            return True
        try:
            acquired = await client.set(
                SCHEDULER_TICK_LOCK_KEY,
                _now().isoformat(),
                nx=True,
                ex=SCHEDULER_TICK_LOCK_TTL_SECONDS,
            )
            if not acquired:
                logger.info("scheduler tick skipped because another worker holds the lock")
            return bool(acquired)
        except Exception as exc:
            logger.warning("scheduler tick lock unavailable, continuing in compatibility mode: %s", exc)
            return True

    async def _claim_due_task(
        self,
        session: AsyncSession,
        task: AutomationTask,
        now: datetime,
    ) -> bool:
        if task.next_run_at is None:
            return False
        claim_until = now + timedelta(minutes=max(task.interval_minutes, 5))
        result = await session.execute(
            update(AutomationTask)
            .where(
                AutomationTask.id == task.id,
                AutomationTask.enabled.is_(True),
                AutomationTask.next_run_at == task.next_run_at,
                AutomationTask.next_run_at <= now,
            )
            .values(next_run_at=claim_until, updated_at=now)
        )
        claimed = bool(getattr(result, "rowcount", 0) == 1)
        if not claimed:
            logger.info("scheduler task claim skipped task_id=%s task_type=%s", task.id, task.task_type)
        return claimed

    async def run_automation_once(self) -> dict[str, object]:
        self.running = True
        self.last_started_at = _now().isoformat()
        self.last_error = ""
        processed = 0
        try:
            factory = get_main_session_factory()
            async with factory() as session:
                rows = await session.execute(
                    select(UserConfig).where(
                        UserConfig.automation_enabled.is_(True),
                        UserConfig.automation_dry_run.is_(True),
                    )
                )
                for cfg in rows.scalars().all():
                    task_row = await session.execute(
                        select(AutomationTask).where(
                            AutomationTask.user_id == cfg.user_id,
                            AutomationTask.tenant_id == cfg.tenant_id,
                            AutomationTask.task_type == "automation_dry_run",
                        )
                    )
                    task = task_row.scalar_one_or_none()
                    if task and not task.enabled:
                        continue
                    started_at = _now()
                    status, message = await _run_dry_run_for_config(session, cfg, started_at)
                    await record_task_run(
                        session,
                        cfg.user_id,
                        cfg.tenant_id,
                        "automation_dry_run",
                        status,
                        message,
                        started_at=started_at,
                    )
                    # Hermes webhook 通知（fire-and-forget）
                    asyncio.create_task(_notify_hermes_async("automation_dry_run", status, message))
                    processed += 1
                await session.commit()
            self.last_message = f"自动 dry-run 完成，处理 {processed} 个配置"
            return {"ok": True, "processed": processed, "message": self.last_message}
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("automation task failed")
            return {"ok": False, "processed": processed, "message": self.last_error}
        finally:
            self.running = False
            self.last_finished_at = _now().isoformat()

    async def run_automation_for_user(
        self,
        session: AsyncSession,
        user_id: int,
        tenant_id: int,
    ) -> dict[str, object]:
        self.running = True
        self.last_started_at = _now().isoformat()
        self.last_error = ""
        processed = 0
        try:
            cfg_result = await session.execute(
                select(UserConfig).where(
                    UserConfig.user_id == user_id,
                    UserConfig.tenant_id == tenant_id,
                    UserConfig.automation_enabled.is_(True),
                    UserConfig.automation_dry_run.is_(True),
                )
            )
            cfg = cfg_result.scalar_one_or_none()
            if not cfg:
                self.last_message = "当前用户未启用自动 dry-run"
                return {"ok": True, "processed": 0, "message": self.last_message}

            task_row = await session.execute(
                select(AutomationTask).where(
                    AutomationTask.user_id == user_id,
                    AutomationTask.tenant_id == tenant_id,
                    AutomationTask.task_type == "automation_dry_run",
                )
            )
            task = task_row.scalar_one_or_none()
            if task and not task.enabled:
                self.last_message = "当前用户自动 dry-run 任务未启用"
                return {"ok": True, "processed": 0, "message": self.last_message}

            started_at = _now()
            status, message = await _run_dry_run_for_config(session, cfg, started_at)
            await record_task_run(
                session,
                user_id,
                tenant_id,
                "automation_dry_run",
                status,
                message,
                started_at=started_at,
            )
            asyncio.create_task(_notify_hermes_async("automation_dry_run", status, message))
            processed = 1
            self.last_message = f"当前用户自动 dry-run 完成，处理 {processed} 个配置"
            return {"ok": status != "failed", "processed": processed, "message": message or self.last_message}
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("user automation task failed user_id=%s tenant_id=%s", user_id, tenant_id)
            return {"ok": False, "processed": processed, "message": self.last_error}
        finally:
            self.running = False
            self.last_finished_at = _now().isoformat()

    async def run_due_tasks_once(self) -> dict[str, object]:
        if not await self._acquire_scheduler_tick_lock():
            return {"ok": True, "processed": 0, "message": "另一工作进程正在扫描到期任务"}
        self.running = True
        self.last_started_at = _now().isoformat()
        self.last_error = ""
        processed = 0
        try:
            factory = get_main_session_factory()
            async with factory() as session:
                now = _now()
                rows = await session.execute(
                    select(AutomationTask).where(
                        AutomationTask.enabled.is_(True),
                        AutomationTask.next_run_at.is_not(None),
                        AutomationTask.next_run_at <= now,
                    )
                )
                for task in rows.scalars().all():
                    started_at = _now()
                    if not await self._claim_due_task(session, task, now):
                        continue
                    await self._run_due_task(session, task, started_at)
                    processed += 1
                await session.commit()
            self.last_message = f"到期任务扫描完成，处理 {processed} 个任务"
            return {"ok": True, "processed": processed, "message": self.last_message}
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("due task scan failed")
            return {"ok": False, "processed": processed, "message": self.last_error}
        finally:
            self.running = False
            self.last_finished_at = _now().isoformat()

    def start_background_loop(self) -> None:
        if self._loop_task and not self._loop_task.done():
            return
        self._stop_event = asyncio.Event()
        self._loop_task = asyncio.create_task(self._loop())
        asyncio.create_task(resolve_pending_orders())

    async def stop_background_loop(self) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._loop_task:
            await self._loop_task

    async def _loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=60)
            except TimeoutError:
                await self.run_due_tasks_once()


task_runtime = TaskRuntime()
