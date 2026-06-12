"""Risk event persistence helpers."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.model.tenant_models import RiskEvent


async def record_risk_event(
    session: AsyncSession,
    *,
    tenant_id: int,
    user_id: int = 0,
    event_type: str,
    severity: str = "info",
    summary: str = "",
    request_id: str = "",
) -> RiskEvent:
    event = RiskEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        event_type=event_type,
        severity=severity,
        summary=summary[:512],
        request_id=request_id[:64],
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event
