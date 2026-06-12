"""Email notification service using Python standard library."""

from email.message import EmailMessage
import smtplib
import ssl

from app.core.exceptions import ValidationError
from app.core.config import get_settings


def validate_email_config(config: dict[str, object]) -> tuple[str, int, str, str, str]:
    host = str(config.get("smtp_host") or "").strip()
    port = int(config.get("smtp_port") or 0)
    username = str(config.get("smtp_user") or "").strip()
    password = str(config.get("smtp_password") or "")
    recipient = str(config.get("email_to") or "").strip()

    if not host:
        raise ValidationError("SMTP 主机不能为空")
    if port <= 0 or port > 65535:
        raise ValidationError("SMTP 端口无效")
    if not username:
        raise ValidationError("SMTP 邮箱账号不能为空")
    if not password or "****" in password:
        raise ValidationError("SMTP 邮箱密码未配置或仍为掩码")
    if "@" not in recipient:
        raise ValidationError("收件人邮箱格式无效")
    return host, port, username, password, recipient


def send_email(config: dict[str, object], subject: str, body: str) -> None:
    host, port, username, password, recipient = validate_email_config(config)

    message = EmailMessage()
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as client:
            client.login(username, password)
            client.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=15) as client:
        client.starttls(context=ssl.create_default_context())
        client.login(username, password)
        client.send_message(message)


def system_email_config(recipient: str) -> dict[str, object]:
    settings = get_settings()
    sender = settings.system_smtp_from or settings.system_smtp_user
    return {
        "smtp_host": settings.system_smtp_host,
        "smtp_port": settings.system_smtp_port,
        "smtp_user": settings.system_smtp_user,
        "smtp_password": settings.system_smtp_password,
        "email_to": recipient,
        "smtp_from": sender,
    }


def send_system_email(recipient: str, subject: str, body: str) -> None:
    config = system_email_config(recipient)
    if not config["smtp_host"] or not config["smtp_user"]:
        raise ValidationError("系统 SMTP 未配置，无法发送账户安全邮件")
    send_email(config, subject, body)


def build_execution_report(result: dict) -> str:
    lines = [
        "Kenne Index 执行报告",
        f"模式: {result.get('mode', '-')}",
        f"总金额: {result.get('total_usdt', 0)} USDT",
        f"消息: {result.get('message', '')}",
        "",
        "订单:",
    ]
    for order in result.get("orders", []):
        lines.append(
            f"- {order.get('symbol', '-')}: {order.get('status', '-')} "
            f"{order.get('usdt', 0)} USDT @ {order.get('price', 0)}"
        )
    return "\n".join(lines)
