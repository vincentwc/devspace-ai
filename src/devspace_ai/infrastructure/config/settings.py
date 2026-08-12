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
    model_provider: str | None = None

    max_text_chars: int = 50_000
    max_upload_bytes: int = 1_048_576
    default_max_cases: int = 10
    hard_max_cases: int = 30
    model_timeout_seconds: float = 120
    total_timeout_seconds: float = 150
    database_url: str = "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai"
    enable_debug_ui: bool | None = None  # None=按 app_env 推断

    def debug_ui_enabled(self) -> bool:
        if self.enable_debug_ui is not None:
            return self.enable_debug_ui
        return self.app_env in {"local", "test"}
