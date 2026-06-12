import pytest
from httpx import AsyncClient
from app.core.metrics import DCA_EXECUTIONS
from app.service.task_service import record_task_run
from tests.conftest import get_test_factory


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    """测试 /metrics 接口能被成功访问且包含自定义指标。"""
    response = await client.get("/metrics")
    assert response.status_code == 200
    content = response.text
    assert "dca_executions_total" in content
    assert "dca_amount_total" in content
    assert "exchange_api_errors_total" in content
    assert "task_failures_total" in content


@pytest.mark.asyncio
async def test_custom_metrics_inc(client: AsyncClient):
    """测试直接或间接更新监控指标时能被体现在端点中。"""
    DCA_EXECUTIONS.labels(symbol="BTC", status="dry_run", mode="dry_run").inc()
    
    response = await client.get("/metrics")
    assert 'dca_executions_total{mode="dry_run",status="dry_run",symbol="BTC"}' in response.text


@pytest.mark.asyncio
async def test_task_failures_metric_integration(client: AsyncClient):
    """测试在 record_task_run 中发生失败时，TASK_FAILURES 能累加更新。"""
    factory = get_test_factory()
    
    async with factory() as session:
        await record_task_run(
            session=session,
            user_id=1,
            tenant_id=1,
            task_type="automation_live",
            status="failed",
            message="Simulated failure for metric testing",
        )
        await session.commit()
        
    response = await client.get("/metrics")
    assert 'task_failures_total{task_id="1_automation_live",task_type="automation_live"}' in response.text
