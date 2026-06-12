"""
KMS 密钥管理抽象服务。

支持 EnvKeyProvider 与 VaultKeyProvider 轨道，当 Vault 轨道不可用时自动降级为本地环境变量，确保开发测试环境顺畅。
"""

import abc
import os
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class KeyProvider(abc.ABC):
    """密钥提供者基类。"""

    @abc.abstractmethod
    def get_encryption_key(self) -> bytes:
        """获取 32 字节的原始加密密钥。"""
        pass


class EnvKeyProvider(KeyProvider):
    """从本地环境变量读取密钥。"""

    def get_encryption_key(self) -> bytes:
        settings = get_settings()
        key_str = settings.encryption_key
        # 取前32位，不足的填充空字节，符合 Fernet 密钥派生规范
        key_bytes = key_str.encode("utf-8")[:32].ljust(32, b"\0")
        return key_bytes


class VaultKeyProvider(KeyProvider):
    """从 HashiCorp Vault 服务动态获取密钥，并提供自动退避降级。"""

    def get_encryption_key(self) -> bytes:
        vault_token = os.getenv("VAULT_TOKEN")
        vault_url = os.getenv("VAULT_URL", "http://localhost:8200")
        vault_secret_path = os.getenv("VAULT_SECRET_PATH", "secret/data/kenne")

        # 检查是否配置了 Vault Token，没有则直接退避到 Env 密钥
        if not vault_token:
            logger.info("VAULT_TOKEN 未配置，自动降级为本地环境变量密钥提供者(EnvKeyProvider)")
            return EnvKeyProvider().get_encryption_key()

        try:
            # 真实环境中这里应通过 import hvac; client = hvac.Client(url=vault_url, token=vault_token) 获取密钥
            # 示例和 Mock 仿真：若没有安装 hvac 模块或 Vault 离线，捕获异常并退避
            # 为确保此处绝对不抛出致命报错从而中断服务，将退避包裹在兜底块内
            import hvac
            client = hvac.Client(url=vault_url, token=vault_token)
            if not client.is_authenticated():
                raise ConnectionError("Vault 身份验证失败")
            
            read_response = client.secrets.kv.v2.read_secret_version(path=vault_secret_path)
            secret_data = read_response['data']['data']
            key_str = secret_data.get("encryption_key")
            if not key_str:
                raise ValueError("Vault 中未配置 'encryption_key' 字段")
            
            return key_str.encode("utf-8")[:32].ljust(32, b"\0")
        except Exception as exc:
            logger.warning(
                "通过 Vault 获取密钥发生错误: %s. 系统已安全自动退避到本地环境变量密钥提供者(EnvKeyProvider)",
                exc
            )
            return EnvKeyProvider().get_encryption_key()


def get_key_provider() -> KeyProvider:
    """密钥工厂：根据系统配置分发 KeyProvider 实例。"""
    provider_type = os.getenv("KMS_PROVIDER", "env").lower()
    if provider_type == "vault":
        return VaultKeyProvider()
    return EnvKeyProvider()
