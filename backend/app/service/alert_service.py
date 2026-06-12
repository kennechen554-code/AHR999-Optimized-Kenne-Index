"""
多渠道告警服务。

支持 Telegram Bot, Discord Webhook 和系统级 SMTP 邮件告警。
"""

import logging
import httpx
from app.core.config import get_settings
from app.service.email_service import send_system_email

logger = logging.getLogger(__name__)


async def send_telegram_alert(bot_token: str, chat_id: str, title: str, message: str) -> bool:
    """发送 Telegram 消息告警。"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"⚠️ *{title}*\n\n{message}",
        "parse_mode": "Markdown"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("Telegram alert sent successfully")
                return True
            logger.error("Telegram alert failed with status %d: %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Telegram alert connection failed: %s", e)
    return False


async def send_discord_alert(webhook_url: str, title: str, message: str) -> bool:
    """发送 Discord Webhook 告警。"""
    payload = {
        "embeds": [
            {
                "title": f"⚠️ {title}",
                "description": message,
                "color": 15158332  # Red
            }
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code in (200, 204):
                logger.info("Discord alert sent successfully")
                return True
            logger.error("Discord alert failed with status %d: %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Discord alert connection failed: %s", e)
    return False


def send_email_alert(recipient: str, title: str, message: str) -> bool:
    """发送邮件告警。"""
    try:
        send_system_email(
            recipient=recipient,
            subject=f"[Kenne Index Alert] {title}",
            body=message
        )
        logger.info("Email alert sent successfully")
        return True
    except Exception as e:
        logger.error("Email alert failed: %s", e)
        return False


async def send_alert(
    title: str,
    message: str,
    severity: str = "warning"
) -> dict[str, bool]:
    """
    通过配置好的多渠道发送系统告警。
    
    Returns:
        {"telegram": bool, "discord": bool, "email": bool} 各通道的发送成功状态。
    """
    settings = get_settings()
    results = {"telegram": False, "discord": False, "email": False}
    
    try:
        # 1. Telegram
        if settings.alert_telegram_bot_token and settings.alert_telegram_chat_id:
            results["telegram"] = await send_telegram_alert(
                settings.alert_telegram_bot_token,
                settings.alert_telegram_chat_id,
                title,
                message
            )
            
        # 2. Discord
        if settings.alert_discord_webhook_url:
            results["discord"] = await send_discord_alert(
                settings.alert_discord_webhook_url,
                title,
                message
            )
            
        # 3. Email
        if settings.system_alert_recipient:
            results["email"] = send_email_alert(settings.system_alert_recipient, title, message)
            
    except Exception as exc:
        logger.error("Failed to dispatch alert title=%s: %s", title, exc)
        
    logger.info("Alert dispatch completed. title=%s results=%s", title, results)
    return results
