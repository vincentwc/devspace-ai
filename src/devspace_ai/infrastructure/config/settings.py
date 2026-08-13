"""环境配置（pydantic-settings）。

空字符串会被当成「未设置」(None)，避免 `.env` 里 `ENABLE_DEBUG_UI=` 这类写法把布尔解析打挂。
"""

from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str = "gpt-4o-mini"
    # None / 其他值 + 有 key → openai_compatible；fake 或无 key → FakeModel
    model_provider: str | None = None

    max_text_chars: int = 50_000
    max_upload_bytes: int = 1_048_576
    default_max_cases: int = 10
    hard_max_cases: int = 30
    model_timeout_seconds: float = 120
    # 覆盖整次 generate（含 repair 重试），应略大于 model_timeout
    total_timeout_seconds: float = 150
    # 默认映射到 compose 对外端口 55432（宿主 5432 常被占用）
    database_url: str = "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai"
    enable_debug_ui: bool | None = None  # None=按 app_env 推断

    @field_validator(
        "model_base_url",
        "model_api_key",
        "model_provider",
        "enable_debug_ui",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value

    def debug_ui_enabled(self) -> bool:
        """显式开关优先；否则仅 local/test 环境开启调试页。"""
        if self.enable_debug_ui is not None:
            return self.enable_debug_ui
        return self.app_env in {"local", "test"}

    def uses_fake_model(self) -> bool:
        """与 factory 同一规则：显式 fake 或没有 API Key 时走 Fake。"""
        return self.model_provider == "fake" or not self.model_api_key

    def effective_model_label(self) -> str:
        if self.uses_fake_model():
            return "fake"
        return self.model_name
