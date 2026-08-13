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


def test_uses_fake_model_without_key() -> None:
    s = Settings(_env_file=None, model_api_key=None, model_provider=None)
    assert s.uses_fake_model() is True
    assert s.effective_model_label() == "fake"


def test_uses_real_model_when_key_present() -> None:
    s = Settings(
        _env_file=None,
        model_api_key="sk-test",
        model_base_url="https://example.com/v1",
        model_provider="openai_compatible",
        model_name="deepseek-chat",
    )
    assert s.uses_fake_model() is False
    assert s.effective_model_label() == "deepseek-chat"


def test_explicit_fake_provider_wins_over_key() -> None:
    s = Settings(_env_file=None, model_api_key="sk-test", model_provider="fake")
    assert s.uses_fake_model() is True
    assert s.effective_model_label() == "fake"
