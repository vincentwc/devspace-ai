import asyncio

from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.factory import build_model_adapter
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter


def test_fake_returns_structured_drafts():
    adapter = FakeModelAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        adapter.generate_case_drafts(
            "登录需求",
            max_cases=10,
            language="zh-CN",
            domain_hint=None,
            repair_issues=None,
        )
    )
    assert 2 <= len(result.raw_drafts) <= 3
    datas = [s.get("test_data") for d in result.raw_drafts for s in d["steps"]]
    assert None in datas
    assert any(x for x in datas if x)


def test_factory_defaults_to_fake_without_key():
    s = Settings(_env_file=None, model_api_key=None, model_provider=None)
    assert isinstance(build_model_adapter(s), FakeModelAdapter)
