"""
结构化 JSON 日志系统与敏感数据脱敏过滤器。
"""

import json
import logging
import re
from app.core.request_id import request_id_ctx

# 敏感关键字遮蔽正则表达式
SENSITIVE_PATTERNS = [
    re.compile(
        r'(?i)(api_key|api_secret|api_passphrase|password|hashed_password|token|access_token|refresh_token|secret_key|encryption_key|stripe_secret_key|mfa_secret|secret|smtp_password)\s*([:=])\s*([\'"]?)([^\s\'",]+)\3'
    ),
]


def mask_sensitive_data(text: str) -> str:
    """自动匹配并遮蔽文本中的敏感字段值。"""
    if not isinstance(text, str):
        return text
    for pattern in SENSITIVE_PATTERNS:
        # 用 ****** 遮蔽值部分，保留关键字和引号样式
        text = pattern.sub(r'\1\2\3******\3', text)
    return text


class SensitiveFilter(logging.Filter):
    """日志敏感字段脱敏过滤器。"""

    def filter(self, record: logging.LogRecord) -> bool:
        # 对主消息文本进行脱敏
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_data(record.msg)
        
        # 对日志参数进行脱敏
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(mask_sensitive_data(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
            
        return True


class StructuredJSONFormatter(logging.Formatter):
    """自定义结构化 JSON 日志格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        # 构建结构化日志基础字段
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get() or "",
        }

        # 兜底脱敏主消息
        log_data["message"] = mask_sensitive_data(log_data["message"])

        # 提取异常堆栈并对其执行脱敏
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            log_data["exception"] = mask_sensitive_data(record.exc_text)

        # 包含日志调用位置
        log_data["filename"] = record.filename
        log_data["lineno"] = record.lineno

        # 支持用户通过 extra= 传入的非内置属性
        for key, val in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "module", "msecs",
                "message", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName"
            ):
                log_data[key] = val

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """初始化并全局应用结构化日志配置。"""
    root = logging.getLogger()
    
    # 清理所有现有 handler
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # 声明控制台输出 handler 并绑定格式化器
    console_handler = logging.StreamHandler()
    console_formatter = StructuredJSONFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(console_formatter)

    # 声明敏感词过滤器
    sensitive_filter = SensitiveFilter()
    console_handler.addFilter(sensitive_filter)

    # 将 handler 挂载到 root logger
    root.addHandler(console_handler)
    root.setLevel(logging.INFO)

    # 替换 uvicorn 及 fastapi 日志 handler，禁止其独立输出明文
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"):
        sub_logger = logging.getLogger(logger_name)
        sub_logger.handlers = [console_handler]
        sub_logger.propagate = False
