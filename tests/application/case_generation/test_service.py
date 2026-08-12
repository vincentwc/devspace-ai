import httpx
import pytest

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.port.outbound.model_port import ModelGenerationResult
from devspace_ai.domain.run.models import GenerationRun, RunStatus
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter

_VALID_DRAFT: dict[str, object] = {
    "title": "主路径验证",
    "preconditions": ["系统可用"],
    "steps": [
        {"action": "打开功能入口", "expected": "页面加载成功", "test_data": None},
        {"action": "提交合法数据", "expected": "操作成功", "test_data": "user=demo"},
    ],
    "priority": "P1",
    "tags": ["fake"],
    "rationale": "ok",
}

_INVALID_DRAFT: dict[str, object] = {
    "title": "",
    "preconditions": [],
    "steps": [],
    "priority": "P1",
    "tags": [],
    "rationale": None,
}


class InMemoryRunRepository:
    def __init__(self) -> None:
        self.store: dict[str, GenerationRun] = {}

    def save(self, run: GenerationRun) -> None:
        self.store[run.run_id] = run

    def get(self, run_id: str) -> GenerationRun | None:
        return self.store.get(run_id)

    def list_recent(self, limit: int = 20) -> list[GenerationRun]:
        return list(self.store.values())[:limit]


class ScriptedModel:
    def __init__(self, responses: list[list[dict[str, object]]]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.repair_calls = 0

    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
    ) -> ModelGenerationResult:
        self.calls += 1
        if repair_issues is not None:
            self.repair_calls += 1
        raw = self._responses.pop(0)
        return ModelGenerationResult(
            raw_drafts=raw[:max_cases],
            model="scripted",
            prompt_tokens=0,
            completion_tokens=0,
        )


@pytest.mark.asyncio
async def test_happy_path_succeeded() -> None:
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=FakeModelAdapter(),
        runs=repo,
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert result.status == RunStatus.SUCCEEDED
    assert len(result.drafts) >= 2
    assert repo.get(result.run_id) is not None


@pytest.mark.asyncio
async def test_max_cases_hard_limit() -> None:
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=FakeModelAdapter(),
        runs=InMemoryRunRepository(),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(
            GenerateCaseDraftsCommand(text="x", file_name=None, file_bytes=None, max_cases=31)
        )
    assert ei.value.code == "MAX_CASES_EXCEEDED"


@pytest.mark.asyncio
async def test_xor_input() -> None:
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=FakeModelAdapter(),
        runs=InMemoryRunRepository(),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(GenerateCaseDraftsCommand(text="x", file_name="a.txt", file_bytes=b"x"))
    assert ei.value.code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_xor_zero_input() -> None:
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=FakeModelAdapter(),
        runs=InMemoryRunRepository(),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(GenerateCaseDraftsCommand(text=None, file_name=None, file_bytes=None))
    assert ei.value.code == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_repair_retry_then_succeeded() -> None:
    model = ScriptedModel([[_INVALID_DRAFT], [_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert model.calls == 2
    assert model.repair_calls == 1
    assert result.status == RunStatus.SUCCEEDED
    assert len(result.drafts) == 1
    assert result.issues == []
    assert repo.get(result.run_id) is not None


@pytest.mark.asyncio
async def test_partial_status_mixed_valid_invalid() -> None:
    model = ScriptedModel(
        [
            [_INVALID_DRAFT],
            [_VALID_DRAFT, _INVALID_DRAFT],
        ]
    )
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert model.calls == 2
    assert result.status == RunStatus.PARTIAL
    assert len(result.drafts) == 1
    assert any(i.code == "DRAFT_VALIDATION_FAILED" for i in result.issues)
    assert repo.get(result.run_id) is not None


class TimeoutModel:
    async def generate_case_drafts(self, *args: object, **kwargs: object) -> None:
        raise TimeoutError("model timed out")


class HttpxTimeoutModel:
    async def generate_case_drafts(self, *args: object, **kwargs: object) -> None:
        raise httpx.TimeoutException("httpx timed out")


class ConnectionErrorModel:
    async def generate_case_drafts(self, *args: object, **kwargs: object) -> None:
        raise ConnectionError("upstream unavailable")


@pytest.mark.asyncio
async def test_model_timeout_persists_failed_run() -> None:
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=TimeoutModel(),
        runs=repo,
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert result.status == RunStatus.FAILED
    assert result.issues[0].code == "MODEL_TIMEOUT"
    assert repo.get(result.run_id) is not None


@pytest.mark.asyncio
async def test_httpx_timeout_maps_to_model_timeout() -> None:
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=HttpxTimeoutModel(),
        runs=repo,
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert result.status == RunStatus.FAILED
    assert result.issues[0].code == "MODEL_TIMEOUT"
    assert repo.get(result.run_id) is not None


@pytest.mark.asyncio
async def test_unexpected_error_persists_failed_run() -> None:
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=ConnectionErrorModel(),
        runs=repo,
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert result.status == RunStatus.FAILED
    assert result.issues[0].code == "INTERNAL_ERROR"
    assert repo.get(result.run_id) is not None
