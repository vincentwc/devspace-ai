import json

import httpx
import pytest

from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.openai_compatible import OpenAICompatibleModelAdapter


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
