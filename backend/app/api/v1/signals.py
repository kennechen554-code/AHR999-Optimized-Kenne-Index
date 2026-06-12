"""
信号查询 API 路由。
"""

import json
import logging
import time
from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.engine.kenne_index import compute_signal, compute_signal_with_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["信号"])


@router.get("")
async def get_signals(user: CurrentUser) -> list[dict]:
    """
    计算所有币种的 Kenne Index 信号。

    每次调用自动执行幂律重拟合，并将参数持久化到 model_params.json。
    """
    settings = get_settings()
    model_params: dict = {}

    # 尝试加载已有参数
    if settings.model_params_path.exists():
        try:
            model_params = json.loads(settings.model_params_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("模型参数读取失败，将重新生成: %s", exc)

    results: list[dict] = []
    for symbol, csv_path in settings.data_files.items():
        signal = compute_signal(csv_path, symbol)

        if not signal.error:
            model_params[symbol] = {
                "slope": signal.slope,
                "r2": signal.r2,
                "data_years": signal.data_years,
                "updated_at": date.today().isoformat(),
            }

        results.append(signal.__dict__)

    # 保存重拟合参数
    try:
        settings.model_params_path.write_text(
            json.dumps(model_params, indent=2, ensure_ascii=False)
        )
    except Exception as exc:
        logger.warning("参数保存失败: %s", exc)

    return results


_public_cache: dict = {
    "data": None,
    "expires_at": 0.0
}


@router.get("/public")
async def get_public_signals() -> list[dict]:
    """
    匿名公开接口：获取币种最新的 Kenne Index 以及 180 天历史走势数据。
    包含 5 分钟的内存缓存以防被匿名流量刷爆。
    """
    now = time.time()
    if _public_cache["data"] is not None and now < _public_cache["expires_at"]:
        return _public_cache["data"]

    settings = get_settings()
    results: list[dict] = []
    for symbol, csv_path in settings.data_files.items():
        res = compute_signal_with_history(csv_path, symbol, history_days=180)
        results.append(res)

    _public_cache["data"] = results
    _public_cache["expires_at"] = now + 300.0  # 缓存 5 分钟
    return results
