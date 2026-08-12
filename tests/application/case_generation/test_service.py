import pytest

from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.domain.run.models import GenerationRun, RunStatus
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter


class InMemoryRunRepository:
    def __init__(self) -> None:
        self.store: dict[str, GenerationRun] = {}

    def save(self, run: GenerationRun) -> None:
        self.store[run.run_id] = run

    def get(self, run_id: str) -> GenerationRun | None:
        return self.store.get(run_id)

    def list_recent(self, limit: int = 20) -> list[GenerationRun]:
        return list(self.store.values())[:limit]


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
            GenerateCaseDraftsCommand(
                text="x", file_name=None, file_bytes=None, max_cases=31
            )
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
        await svc.generate(
            GenerateCaseDraftsCommand(text="x", file_name="a.txt", file_bytes=b"x")
        )
    assert ei.value.code == "INVALID_INPUT"


class TimeoutModel:
    async def generate_case_drafts(self, *args: object, **kwargs: object) -> None:
        raise TimeoutError("model timed out")


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
