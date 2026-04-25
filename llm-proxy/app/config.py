"""
配置加载模块
"""

from pathlib import Path
from functools import lru_cache

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class AppConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    secret_key: str = ""
    jwt_secret: str = ""


class DatabaseConfig(BaseModel):
    host: str = "localhost"
    port: int = 3306
    username: str = "root"
    password: str = ""
    name: str = "llm_proxy"

    @property
    def url(self) -> str:
        return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""


class EmailConfig(BaseModel):
    resend_api_key: str = ""
    from_email: str = ""
    from_name: str = "LLM Proxy"


class UpstreamConfig(BaseModel):
    base_url: str = ""
    gemini_base_url: str = ""
    api_key: str = ""
    timeout: int = 120


class BillingConfig(BaseModel):
    min_charge: float = 0.01
    free_balance: float = 0.00


class SessionConfig(BaseModel):
    ttl: int = 86400
    cookie_name: str = "llm_session"
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = "none"  # 跨域必须设为 none（配合 secure=True）


class RateLimitConfig(BaseModel):
    verify_code_per_minute: int = 1
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15


class PayPalConfig(BaseModel):
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    client_id: str = ""
    client_secret: str = ""
    proxy: str = ""


class Settings(BaseSettings):
    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    email: EmailConfig = EmailConfig()
    upstream: UpstreamConfig = UpstreamConfig()
    billing: BillingConfig = BillingConfig()
    session: SessionConfig = SessionConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    paypal: PayPalConfig = PayPalConfig()

    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"


def load_config_from_yaml(config_path: str = "config.yaml") -> dict:
    """从 YAML 文件加载配置"""
    path = Path(config_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    config_data = load_config_from_yaml()
    return Settings(**config_data)


settings = get_settings()
