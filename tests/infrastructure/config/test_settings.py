from pytest import MonkeyPatch

from devspace_ai.infrastructure.config.settings import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.max_text_chars == 50_000
    assert s.max_upload_bytes == 1_048_576
    assert s.default_max_cases == 10
    assert s.hard_max_cases == 30
    assert s.model_timeout_seconds == 120
    assert s.total_timeout_seconds == 150


def test_empty_env_strings_become_none(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_DEBUG_UI", "")
    monkeypatch.setenv("MODEL_API_KEY", "")
    monkeypatch.setenv("MODEL_PROVIDER", "")
    monkeypatch.setenv("MODEL_BASE_URL", "")
    s = Settings(_env_file=None)
    assert s.enable_debug_ui is None
    assert s.model_api_key is None
    assert s.model_provider is None
    assert s.model_base_url is None
    assert s.debug_ui_enabled() is True  # app_env default local
