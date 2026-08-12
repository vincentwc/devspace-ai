from __future__ import annotations

import json
from typing import Any

import httpx

from devspace_ai.application.port.outbound.model_port import ModelGenerationResult
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.prompt.case_generation import build_messages


class OpenAICompatibleModelAdapter:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
    ) -> ModelGenerationResult:
        if not self.settings.model_base_url:
            raise RuntimeError("MODEL_BASE_URL is required for openai_compatible provider")
        messages = build_messages(
            requirement_text,
            max_cases=max_cases,
            language=language,
            domain_hint=domain_hint,
            repair_issues=repair_issues,
        )
        url = self.settings.model_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.model_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.settings.model_name,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(
            timeout=self.settings.model_timeout_seconds,
            transport=self.transport,
        ) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        drafts = parsed["drafts"] if isinstance(parsed, dict) and "drafts" in parsed else parsed
        usage = data.get("usage") or {}
        return ModelGenerationResult(
            raw_drafts=list(drafts),
            model=data.get("model") or self.settings.model_name,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
