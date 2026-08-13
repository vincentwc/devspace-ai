from uuid import uuid4

import httpx
import pytest

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.port.outbound.model_port import ModelGenerationResult
from devspace_ai.application.style_pack.service import StylePackService
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.run.models import GenerationRun, RunStatus
from devspace_ai.domain.style_pack.models import StyleExample, StylePack
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter
from devspace_ai.infrastructure.style_pack.builtins import BUILTIN_PAYMENT_ID

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
        self.style_pack: object | None = None

    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
        style_pack: object | None = None,
    ) -> ModelGenerationResult:
        self.style_pack = style_pack
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
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
        style_packs=_style_packs(),
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert result.status == RunStatus.FAILED
    assert result.issues[0].code == "INTERNAL_ERROR"
    assert repo.get(result.run_id) is not None


class EmptyStylePackRepository:
    """生成测试只需 get；未知 id 走仓储 miss → PackNotFoundError。"""

    def list_user(self) -> list[StylePack]:
        return []

    def get(self, id: str) -> StylePack | None:
        return None

    def create(self, pack: StylePack) -> StylePack:
        raise NotImplementedError

    def update(self, pack: StylePack) -> StylePack | None:
        return None

    def delete(self, id: str) -> bool:
        return False

    def count(self) -> int:
        return 0

    def get_by_key(self, key: str) -> StylePack | None:
        return None


def _style_packs() -> StylePackService:
    return StylePackService(EmptyStylePackRepository())


@pytest.mark.asyncio
async def test_generate_with_builtin_style_pack_loads_context() -> None:
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
        style_packs=_style_packs(),
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(
            text="用户登录",
            file_name=None,
            file_bytes=None,
            style_pack_id=BUILTIN_PAYMENT_ID,
        )
    )
    assert model.style_pack is not None
    assert any(s.step_name == "load_style_context" for s in result.trace.steps)
    step = next(s for s in result.trace.steps if s.step_name == "load_style_context")
    assert result.style_pack is not None
    assert result.style_pack.builtin is True
    assert step.summary == (
        f"{result.style_pack.name}（{result.style_pack.key}），"
        f"需求 {len(result.style_pack.examples)} 组，"
        f"用例 {result.style_pack.draft_count()} 条"
    )


@pytest.mark.asyncio
async def test_generate_without_style_pack_omits_load_step() -> None:
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
        style_packs=_style_packs(),
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None)
    )
    assert model.style_pack is None
    assert all(s.step_name != "load_style_context" for s in result.trace.steps)
    assert result.style_pack is None


@pytest.mark.asyncio
async def test_generate_empty_style_pack_id_is_unselected() -> None:
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
        style_packs=_style_packs(),
    )
    result = await svc.generate(
        GenerateCaseDraftsCommand(
            text="用户登录",
            file_name=None,
            file_bytes=None,
            style_pack_id="",
        )
    )
    assert model.style_pack is None
    assert result.style_pack is None
    assert all(s.step_name != "load_style_context" for s in result.trace.steps)


@pytest.mark.asyncio
async def test_generate_unknown_style_pack_rejects_without_run() -> None:
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
        style_packs=_style_packs(),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(
            GenerateCaseDraftsCommand(
                text="用户登录",
                file_name=None,
                file_bytes=None,
                style_pack_id="00000000-0000-4000-8000-000000000099",
            )
        )
    assert ei.value.code == "PACK_NOT_FOUND"
    assert model.calls == 0
    assert repo.store == {}


@pytest.mark.asyncio
async def test_generate_invalid_style_pack_id_rejects_without_model() -> None:
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
        style_packs=_style_packs(),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(
            GenerateCaseDraftsCommand(
                text="用户登录",
                file_name=None,
                file_bytes=None,
                style_pack_id="abc",
            )
        )
    assert ei.value.code == "INVALID_INPUT"
    assert model.calls == 0
    assert repo.store == {}


@pytest.mark.asyncio
async def test_generate_style_pack_combined_length_too_long() -> None:
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None, max_text_chars=50),
        model=model,
        runs=repo,
        style_packs=_style_packs(),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(
            GenerateCaseDraftsCommand(
                text="登录",
                file_name=None,
                file_bytes=None,
                style_pack_id=BUILTIN_PAYMENT_ID,
            )
        )
    assert ei.value.code == "INPUT_TOO_LONG"
    assert "已计入风格包范文" in ei.value.message
    assert "50" in ei.value.message


class StoredInvalidStylePackRepository(EmptyStylePackRepository):
    def __init__(self, pack: StylePack) -> None:
        self._pack = pack

    def get(self, id: str) -> StylePack | None:
        if id == self._pack.id:
            return self._pack
        return None


@pytest.mark.asyncio
async def test_generate_invalid_stored_pack_rejects_without_model() -> None:
    pack = StylePack(
        id=str(uuid4()),
        key="user.broken",
        name="损坏包",
        examples=[
            StyleExample(
                requirement_text="",
                drafts=[
                    CaseDraft(
                        title="无标题步骤",
                        steps=[TestStep(action="a", expected="b")],
                    )
                ],
            )
        ],
    )
    model = ScriptedModel([[_VALID_DRAFT]])
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(
        settings=Settings(_env_file=None),
        model=model,
        runs=repo,
        style_packs=StylePackService(StoredInvalidStylePackRepository(pack)),
    )
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(
            GenerateCaseDraftsCommand(
                text="用户登录",
                file_name=None,
                file_bytes=None,
                style_pack_id=pack.id,
            )
        )
    assert ei.value.code == "INVALID_EXAMPLE"
    assert model.calls == 0
    assert repo.store == {}
