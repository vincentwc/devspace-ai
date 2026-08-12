from devspace_ai.infrastructure.config.settings import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.max_text_chars == 50_000
    assert s.max_upload_bytes == 1_048_576
    assert s.default_max_cases == 10
    assert s.hard_max_cases == 30
    assert s.model_timeout_seconds == 120
    assert s.total_timeout_seconds == 150
