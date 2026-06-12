"""
应用全局配置。

通过 pydantic-settings 从环境变量 / .env 文件加载，
禁止硬编码任何密钥或连接串。
"""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """所有配置项均从环境变量读取，生产环境通过 .env 注入。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── 基础 ──────────────────────────────────────────────
    debug: bool = False
    environment: str = "development"
    project_name: str = "Kenne Index"

    # ─── 数据库 ────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/kenne_main"
    tenant_db_url_template: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/kenne_tenant_{tenant_id}"
    )

    # ─── Redis ─────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_backend: str = "auto"

    # ─── JWT ───────────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cookie_secure: bool = False
    csrf_protection: bool = True
    global_live_trading_enabled: bool = True

    # ─── 加密（AES-256 对称加密 API Key 等）────────────────
    encryption_key: str = "change-me-32-byte-key-in-prod!!"

    # ─── CoinGecko ─────────────────────────────────────────
    coingecko_api_key: str = ""
    glassnode_api_key: str = ""
    researchbitcoin_api_token: str = ""

    # ─── CORS ──────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:5173"]

    # System SMTP is used for account security emails. User SMTP remains for reports.
    system_smtp_host: str = ""
    system_smtp_port: int = 587
    system_smtp_user: str = ""
    system_smtp_password: str = ""
    system_smtp_from: str = ""

    # ─── Stripe ────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_basic_price_id: str = ""
    stripe_premium_price_id: str = ""

    # ─── 告警系统 ──────────────────────────────────────────
    alert_telegram_bot_token: str = ""
    alert_telegram_chat_id: str = ""
    alert_discord_webhook_url: str = ""
    system_alert_recipient: str = ""

    # ─── 数据目录 ──────────────────────────────────────────
    data_dir: Path = Path(__file__).resolve().parent.parent.parent / "data"
    backtest_allowed_dirs: list[Path] = Field(default_factory=list)

    # ─── Hermes Agent Webhook ───────────────────────────────
    hermes_webhook_url: str = ""
    hermes_webhook_secret: str = ""

    @property
    def data_files(self) -> dict[str, Path]:
        """返回各币种 CSV 文件路径映射。"""
        return {
            "BTC": self.data_dir / "btc_4h_data_2018_to_2025.csv",
            "ETH": self.data_dir / "eth_4h_data_2017_to_2025.csv",
            "SOL": self.data_dir / "sol_4h_data_2020_to_2025.csv",
        }

    @property
    def resolved_backtest_allowed_dirs(self) -> list[Path]:
        """Return directories that backtest local-path mode may read from."""
        dirs = [self.data_dir, *self.backtest_allowed_dirs]
        resolved: list[Path] = []
        for item in dirs:
            try:
                path = Path(item).expanduser().resolve()
            except OSError:
                continue
            if path not in resolved:
                resolved.append(path)
        return resolved

    @property
    def model_params_path(self) -> Path:
        return self.data_dir / "model_params.json"

    @property
    def is_production(self) -> bool:
        """Return whether the app is running with production safeguards enabled."""
        return self.environment.lower() in {"prod", "production"}

    def validate_production_settings(self) -> None:
        """Fail fast when production is started with development placeholders."""
        if not self.is_production:
            return

        errors: list[str] = []
        placeholder_secrets = {
            "change-me-in-production",
            "change-me-32-byte-key-in-prod!!",
            "your-super-secret-key-change-in-production",
            "your-32-byte-encryption-key-here",
        }
        if self.debug:
            errors.append("DEBUG must be false")
        if self.secret_key in placeholder_secrets or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be a high-entropy value of at least 32 characters")
        if self.encryption_key in placeholder_secrets or len(self.encryption_key) < 32:
            errors.append("ENCRYPTION_KEY must be a stable high-entropy value of at least 32 characters")
        if any(
            placeholder in self.database_url or placeholder in self.tenant_db_url_template
            for placeholder in ("postgres:password@", "change-this-local-password")
        ):
            errors.append("DATABASE_URL and TENANT_DB_URL_TEMPLATE must not use default credentials")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true behind HTTPS")
        if any(origin == "*" or origin.startswith("http://") for origin in self.cors_origins):
            errors.append("CORS_ORIGINS must contain only trusted HTTPS origins")

        if errors:
            raise RuntimeError("生产配置不安全: " + "; ".join(errors))


# NOTE: 单例模式，全局使用 get_settings() 获取
_settings: Settings | None = None


def get_settings() -> Settings:
    """延迟初始化并缓存 Settings 实例。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
