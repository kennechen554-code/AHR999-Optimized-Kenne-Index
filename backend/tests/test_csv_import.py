"""CSV 导入接口测试。

验证 /api/v1/history/import/preview 和 /api/v1/history/import/confirm 的各种场景。
"""

import io

import pytest
from httpx import AsyncClient

VALID_CSV_HEADER = "ts,symbol,exchange,mode,strategy_mode,usdt,price,qty,kenne_index,mult,momentum,status,order_id,note"
VALID_CSV_ROW = "2026-04-26T01:00:00+00:00,BTC,okx,dry_run,per_asset_strict_dd,100,50000,0.002,0.5,1.0,bullish,dry_run,ord-001,test"
VALID_CSV = f"{VALID_CSV_HEADER}\n{VALID_CSV_ROW}\n"


def _make_csv_file(content: str, filename: str = "import.csv") -> tuple[str, io.BytesIO, str]:
    """构造 multipart 上传用的 CSV 文件元组。"""
    return (filename, io.BytesIO(content.encode("utf-8")), "text/csv")


@pytest.mark.asyncio
async def test_preview_valid_csv(authed_client: AsyncClient) -> None:
    """上传有效 CSV → 预览返回 valid_count=1。"""
    response = await authed_client.post(
        "/api/v1/history/import/preview",
        files={"file": _make_csv_file(VALID_CSV)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid_count"] == 1
    assert data["invalid_count"] == 0
    assert data["duplicate_count"] == 0
    assert len(data["rows"]) == 1


@pytest.mark.asyncio
async def test_preview_invalid_csv_columns(authed_client: AsyncClient) -> None:
    """缺少必需列 → 422。"""
    bad_csv = "ts,symbol\n2026-04-26,BTC\n"
    response = await authed_client.post(
        "/api/v1/history/import/preview",
        files={"file": _make_csv_file(bad_csv)},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_preview_invalid_csv_data(authed_client: AsyncClient) -> None:
    """无效 symbol（DOGE）→ 返回 error 字段。"""
    invalid_row = "2026-04-26T01:00:00+00:00,DOGE,okx,dry_run,per_asset_strict_dd,100,50000,0.002,0.5,1.0,bullish,dry_run,ord-001,test"
    csv_content = f"{VALID_CSV_HEADER}\n{invalid_row}\n"

    response = await authed_client.post(
        "/api/v1/history/import/preview",
        files={"file": _make_csv_file(csv_content)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid_count"] == 0
    assert data["invalid_count"] == 1
    assert data["rows"][0]["error"] != ""


@pytest.mark.asyncio
async def test_confirm_valid_csv(authed_client: AsyncClient) -> None:
    """确认导入有效 CSV → 返回 imported_count=1。"""
    response = await authed_client.post(
        "/api/v1/history/import/confirm",
        files={"file": _make_csv_file(VALID_CSV)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported_count"] == 1
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_confirm_rejects_duplicates(authed_client: AsyncClient) -> None:
    """二次导入相同 CSV → skipped_duplicates > 0。"""
    # 第一次导入
    await authed_client.post(
        "/api/v1/history/import/confirm",
        files={"file": _make_csv_file(VALID_CSV)},
    )

    # 第二次导入相同内容
    response = await authed_client.post(
        "/api/v1/history/import/confirm",
        files={"file": _make_csv_file(VALID_CSV)},
    )
    assert response.status_code == 200
    data = response.json()
    # 重复行被跳过，imported_count 应为 0
    assert data["imported_count"] == 0
    assert data["skipped_duplicates"] >= 1
