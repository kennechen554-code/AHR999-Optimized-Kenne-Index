"""多渠道告警系统单元与集成测试。"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.service.alert_service import send_alert


@pytest.mark.asyncio
async def test_send_alert_all_channels_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Mock 配置项，启用所有告警渠道
    from app.core.config import Settings
    test_settings = Settings(
        alert_telegram_bot_token="fake_bot_token",
        alert_telegram_chat_id="fake_chat_id",
        alert_discord_webhook_url="https://discord.com/api/webhooks/fake",
        system_alert_recipient="alert@test.com",
    )
    monkeypatch.setattr("app.service.alert_service.get_settings", lambda: test_settings)

    # 2. Mock 外部 API 客户端
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200

    mock_send_email = MagicMock()

    with patch("httpx.AsyncClient.post", mock_post):
        with patch("app.service.alert_service.send_system_email", mock_send_email):
            results = await send_alert(
                title="Test Alert Title",
                message="Test Alert Message Content",
                severity="critical"
            )

    # 3. 验证 Telegram 和 Discord 均成功调用 post，且邮件已发送
    assert results["telegram"] is True
    assert results["discord"] is True
    assert results["email"] is True

    # 验证 Telegram 调用细节
    telegram_call = mock_post.call_args_list[0]
    assert "fake_bot_token" in telegram_call[0][0]
    assert telegram_call[1]["json"]["chat_id"] == "fake_chat_id"

    # 验证 Discord 调用细节
    discord_call = mock_post.call_args_list[1]
    assert "fake" in discord_call[0][0]

    # 验证邮件发送调用
    mock_send_email.assert_called_once_with(
        recipient="alert@test.com",
        subject="[Kenne Index Alert] Test Alert Title",
        body="Test Alert Message Content"
    )
