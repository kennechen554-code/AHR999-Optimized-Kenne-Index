"""
用户分享与邀请裂变 API 路由。
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_main_session
from app.core.exceptions import ValidationError, NotFoundError
from app.model.user import User
from app.model.tenant_models import TradeRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/share", tags=["邀请裂变"])


async def _get_current_prices() -> dict[str, float]:
    """获取主要币种最新的市场收盘价，优先读取公开信号缓存。"""
    try:
        from app.api.v1.signals import _public_cache, get_public_signals
        import time
        now = time.time()
        if _public_cache["data"] is None or now >= _public_cache["expires_at"]:
            await get_public_signals()
        
        prices = {}
        if _public_cache["data"]:
            for item in _public_cache["data"]:
                prices[item["symbol"]] = item["price"]
        return prices
    except Exception as exc:
        logger.warning("获取最新价格失败，将使用兜底价格: %s", exc)
        return {"BTC": 65000.0, "ETH": 3500.0, "SOL": 150.0}


def _mask_name(name: str) -> str:
    """脱敏用户显示名。"""
    if not name:
        return "匿名用户"
    if len(name) <= 1:
        return name + "*"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "***" + name[-1]


async def _calculate_user_performance(session: AsyncSession, user: User) -> dict:
    """计算指定用户的定投总收益和表现。"""
    # 1. 查找全部成功交易记录
    stmt = (
        select(TradeRecord)
        .where(
            TradeRecord.tenant_id == user.tenant_id,
            TradeRecord.qty > 0,
            TradeRecord.price > 0
        )
    )
    res = await session.execute(stmt)
    records = res.scalars().all()

    # 按币种统计
    stats = {}
    for r in records:
        sym = r.symbol.upper()
        if sym not in stats:
            stats[sym] = {"cost": 0.0, "qty": 0.0}
        stats[sym]["cost"] += r.usdt
        stats[sym]["qty"] += r.qty

    # 最新价格
    prices = await _get_current_prices()

    total_invested = 0.0
    current_value = 0.0
    assets_list = []

    for sym, stat in stats.items():
        price = prices.get(sym, 1.0)
        value = stat["qty"] * price
        profit = value - stat["cost"]
        profit_rate = (profit / stat["cost"] * 100) if stat["cost"] > 0 else 0.0

        total_invested += stat["cost"]
        current_value += value

        assets_list.append({
            "symbol": sym,
            "cost": round(stat["cost"], 2),
            "qty": round(stat["qty"], 6),
            "current_price": round(price, 2),
            "value": round(value, 2),
            "profit": round(profit, 2),
            "profit_rate": round(profit_rate, 2)
        })

    total_profit = current_value - total_invested
    overall_profit_rate = (total_profit / total_invested * 100) if total_invested > 0 else 0.0

    # 2. 统计受邀人数
    invite_stmt = select(func.count(User.id)).where(User.referred_by_id == user.id)
    invited_count = (await session.execute(invite_stmt)).scalar_one() or 0

    return {
        "referral_code": user.referral_code or "",
        "invited_count": invited_count,
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "total_profit": round(total_profit, 2),
        "profit_rate": round(overall_profit_rate, 2),
        "assets": assets_list
    }


@router.get("/performance")
async def get_share_performance(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    """获取当前登录用户的定投表现及裂变卡片数据。"""
    return await _calculate_user_performance(session, user)


@router.get("/invite-info")
async def get_invite_info(
    code: str,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    """
    根据邀请码拉取邀请人的公开脱敏定投卡片数据。
    
    此为匿名接口，绝对屏蔽敏感金额。
    """
    if not code:
        raise ValidationError("邀请码不能为空")
    
    referrer = (await session.execute(
        select(User).where(User.referral_code == code)
    )).scalar_one_or_none()
    
    if not referrer:
        raise NotFoundError("推荐人邀请码", code)
    
    perf = await _calculate_user_performance(session, referrer)
    
    return {
        "referrer_name": _mask_name(referrer.display_name or referrer.email.split("@")[0]),
        "profit_rate": perf["profit_rate"],
        "invited_count": perf["invited_count"]
    }
