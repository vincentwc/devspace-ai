import json

import httpx
import pytest

from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.openai_compatible import OpenAICompatibleModelAdapter
from devspace_ai.infrastructure.style_pack.builtins import BUILTIN_PAYMENT_ID, get_builtin


@pytest.mark.asyncio
async def test_parses_drafts_from_chat_completion():
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "drafts": [
                                {
                                    "title": "t",
                                    "preconditions": [],
                                    "steps": [
                                        {
                                            "action": "a",
                                            "expected": "e",
                                            "test_data": None,
                                        }
                                    ],
                                    "priority": None,
                                    "tags": [],
                                    "rationale": None,
                                }
                            ]
                        }
                    )
                }
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        "model": "demo",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    settings = Settings(
        _env_file=None,
        model_base_url="https://example.com/v1",
        model_api_key="k",
        model_name="demo",
    )
    adapter = OpenAICompatibleModelAdapter(settings, transport=transport)
    result = await adapter.generate_case_drafts(
        "req",
        max_cases=10,
        language="zh-CN",
        domain_hint=None,
        repair_issues=None,
    )
    assert result.raw_drafts[0]["title"] == "t"
    assert result.prompt_tokens == 1


@pytest.mark.asyncio
async def test_request_body_includes_style_pack_block():
    pack = get_builtin(BUILTIN_PAYMENT_ID)
    assert pack is not None
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps({"drafts": []})}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "model": "demo",
            },
        )

    adapter = OpenAICompatibleModelAdapter(
        Settings(
            _env_file=None,
            model_base_url="https://example.com/v1",
            model_api_key="k",
            model_name="demo",
        ),
        transport=httpx.MockTransport(handler),
    )
    await adapter.generate_case_drafts(
        "用户申请全额退款",
        max_cases=3,
        language="zh-CN",
        domain_hint=None,
        repair_issues=None,
        style_pack=pack,
    )
    body = seen["body"]
    assert isinstance(body, dict)
    messages = body["messages"]
    system = str(messages[0]["content"])
    user = str(messages[1]["content"])
    assert "imitate" in system.lower()
    assert "Style pack:" in user
    assert pack.key in user
    assert pack.examples[0].requirement_text in user
    assert pack.examples[0].drafts[0].title in user
