# Case Draft Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `devspace-ai` v1 so a Jinja debug page can synchronously turn pasted/uploaded requirement text into validated `CaseDraft[]` with run traces, using a thin Agent Graph and Fake/OpenAI-compatible models.

**Architecture:** Lightweight DDD + ports/adapters in Python/FastAPI. Application layer runs fixed Graph `ingest → generate → validate → persist`. Domain owns `CaseDraft`/`GenerationRun` invariants. Infrastructure provides Fake/OpenAI model, multipart ingest, SQLite run store. Interfaces expose REST + Jinja debug UI on the same use case.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Jinja2, Pydantic v2, httpx, SQLite (stdlib), pytest, pytest-asyncio, ruff (optional)

**Spec:** `docs/superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md`

## Global Constraints

- Python ≥ 3.11; package root `src/devspace_ai/` (DDD folders from spec live under this package).
- Sync API only: `POST /api/v1/case-drafts/generate` blocks until Graph finishes or total timeout.
- Public run status: `running | succeeded | failed | partial` (never expose `queued`).
- Status rules (DEC-012): all valid → `succeeded`; ≥1 valid with issues → `partial`; 0 valid → `failed`.
- Reject overlong text (default 50_000 chars) and oversized upload (default 1 MiB) with explicit 4xx `issues`.
- `max_cases` default 10, hard max 30.
- Timeouts: model 120s, HTTP/app total 150s; on timeout persist failed Run with `MODEL_TIMEOUT`.
- `issues[]` shape: `{ code, message, draft_index?, field? }`.
- No TMS write-back; no auth; no SPA; debug UI = Jinja + light JS.
- Default CI green without real API key via deterministic Fake Model.
- Dependencies: do not add LangChain/agent frameworks in v1.

## File Map

| Path | Responsibility |
| --- | --- |
| `pyproject.toml` | Project metadata, deps, pytest config |
| `.env.example` | Documented env vars (no secrets) |
| `README.md` | Run / configure / demo |
| `src/devspace_ai/domain/case_draft/models.py` | `TestStep`, `CaseDraft`, domain validation |
| `src/devspace_ai/domain/case_draft/errors.py` | Domain validation error type |
| `src/devspace_ai/domain/requirement/models.py` | `RequirementDocument`, source enum |
| `src/devspace_ai/domain/run/models.py` | `GenerationRun`, `RunStatus`, `RunTrace`, `StepRecord`, `Issue` |
| `src/devspace_ai/domain/run/status.py` | Status resolution helpers |
| `src/devspace_ai/application/port/outbound/model_port.py` | `ModelPort` protocol |
| `src/devspace_ai/application/port/outbound/run_repository_port.py` | `RunRepositoryPort` |
| `src/devspace_ai/application/port/inbound/generate_case_drafts_port.py` | Inbound port |
| `src/devspace_ai/application/dto/commands.py` | `GenerateCaseDraftsCommand` |
| `src/devspace_ai/application/dto/results.py` | `GenerateCaseDraftsResult` |
| `src/devspace_ai/application/case_generation/service.py` | Graph orchestration |
| `src/devspace_ai/application/case_generation/errors.py` | App-level input errors |
| `src/devspace_ai/infrastructure/config/settings.py` | Env-backed settings |
| `src/devspace_ai/infrastructure/model/fake_model.py` | Deterministic Fake Model |
| `src/devspace_ai/infrastructure/model/openai_compatible.py` | OpenAI-compatible client |
| `src/devspace_ai/infrastructure/model/factory.py` | Choose fake vs real |
| `src/devspace_ai/infrastructure/persistence/sqlite_run_repository.py` | SQLite Run store |
| `src/devspace_ai/infrastructure/prompt/case_generation.py` | Prompt templates |
| `src/devspace_ai/infrastructure/source/text_ingest.py` | Text/file → requirement text |
| `src/devspace_ai/interfaces/rest/schemas.py` | HTTP DTOs |
| `src/devspace_ai/interfaces/rest/errors.py` | Error JSON helpers |
| `src/devspace_ai/interfaces/rest/routes_case_drafts.py` | Generate + get run |
| `src/devspace_ai/interfaces/web_debug/routes.py` | Debug pages |
| `src/devspace_ai/interfaces/web_debug/templates/*.html` | Jinja templates |
| `src/devspace_ai/apps/api/main.py` | App factory / DI wiring |
| `tests/...` | Mirror package paths |

---

### Task 1: Project scaffold + settings + health

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/devspace_ai/__init__.py`
- Create: `src/devspace_ai/infrastructure/config/settings.py`
- Create: `src/devspace_ai/apps/api/main.py`
- Create: `tests/infrastructure/config/test_settings.py`
- Create: `tests/apps/test_health.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Settings` dataclass/pydantic settings; `create_app() -> FastAPI` with `GET /health`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "devspace-ai"
version = "0.1.0"
description = "Reusable AI service for test-domain capabilities"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "jinja2>=3.1.0",
  "python-multipart>=0.0.9",
  "pydantic>=2.8.0",
  "pydantic-settings>=2.4.0",
  "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "anyio>=4.0.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write failing settings test**

```python
# tests/infrastructure/config/test_settings.py
from devspace_ai.infrastructure.config.settings import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.max_text_chars == 50_000
    assert s.max_upload_bytes == 1_048_576
    assert s.default_max_cases == 10
    assert s.hard_max_cases == 30
    assert s.model_timeout_seconds == 120
    assert s.total_timeout_seconds == 150
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/vincent/developEnv/code/ai/devspace-ai && python -m pip install -e ".[dev]" && pytest tests/infrastructure/config/test_settings.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 4: Implement settings + empty packages**

```python
# src/devspace_ai/infrastructure/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str = "gpt-4o-mini"
    model_provider: str | None = None  # openai_compatible | fake | None(auto)

    max_text_chars: int = 50_000
    max_upload_bytes: int = 1_048_576
    default_max_cases: int = 10
    hard_max_cases: int = 30
    model_timeout_seconds: float = 120
    total_timeout_seconds: float = 150
    sqlite_path: str = "data/runs.db"
```

```python
# src/devspace_ai/apps/api/main.py
from fastapi import FastAPI
from devspace_ai.infrastructure.config.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="devspace-ai", version="0.1.0")
    app.state.settings = settings

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
```

Also create empty `__init__.py` files under `src/devspace_ai/` package tree as needed, and `.env.example` listing the settings field names.

- [ ] **Step 5: Write health test and run all Task 1 tests**

```python
# tests/apps/test_health.py
from fastapi.testclient import TestClient
from devspace_ai.apps.api.main import create_app


def test_health():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
```

Run: `pytest tests/infrastructure/config/test_settings.py tests/apps/test_health.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example src/devspace_ai tests
git commit -m "chore: scaffold FastAPI app, settings, and health endpoint"
```

---

### Task 2: Domain CaseDraft + TestStep invariants

**Files:**
- Create: `src/devspace_ai/domain/case_draft/errors.py`
- Create: `src/devspace_ai/domain/case_draft/models.py`
- Create: `tests/domain/case_draft/test_models.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `TestStep(action: str, expected: str, test_data: str | None)`
  - `CaseDraft(title, preconditions: list[str], steps: list[TestStep], priority: str | None, tags: list[str], rationale: str | None)`
  - `CaseDraft.validate() -> None` raises `CaseDraftValidationError`
  - `normalize_test_data(value: str | None) -> str | None` maps `""` → `None`

- [ ] **Step 1: Write failing tests**

```python
# tests/domain/case_draft/test_models.py
import pytest
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.case_draft.errors import CaseDraftValidationError


def test_valid_draft_allows_null_test_data():
    draft = CaseDraft(
        title="登录成功",
        preconditions=["已注册用户"],
        steps=[TestStep(action="输入账号密码", expected="进入首页", test_data=None)],
        priority="P1",
        tags=["auth"],
        rationale="覆盖主路径",
    )
    draft.validate()


def test_empty_test_data_normalized_to_none():
    step = TestStep(action="a", expected="b", test_data="")
    assert step.normalized().test_data is None


def test_rejects_empty_title_or_steps():
    with pytest.raises(CaseDraftValidationError):
        CaseDraft(title=" ", preconditions=[], steps=[TestStep("a", "b", None)], priority=None, tags=[], rationale=None).validate()
    with pytest.raises(CaseDraftValidationError):
        CaseDraft(title="t", preconditions=[], steps=[], priority=None, tags=[], rationale=None).validate()
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/domain/case_draft/test_models.py -v`

- [ ] **Step 3: Implement domain models**

```python
# src/devspace_ai/domain/case_draft/errors.py
class CaseDraftValidationError(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


# src/devspace_ai/domain/case_draft/models.py
from dataclasses import dataclass, field
from .errors import CaseDraftValidationError

ALLOWED_PRIORITIES = {"P0", "P1", "P2", "P3"}


@dataclass(frozen=True)
class TestStep:
    action: str
    expected: str
    test_data: str | None = None

    def normalized(self) -> "TestStep":
        data = self.test_data
        if data is not None and data.strip() == "":
            data = None
        return TestStep(action=self.action.strip(), expected=self.expected.strip(), test_data=data)


@dataclass
class CaseDraft:
    title: str
    preconditions: list[str] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)
    priority: str | None = None
    tags: list[str] = field(default_factory=list)
    rationale: str | None = None

    def validate(self) -> None:
        if not self.title or not self.title.strip():
            raise CaseDraftValidationError("title must be non-empty", field="title")
        if not self.steps:
            raise CaseDraftValidationError("steps must contain at least one item", field="steps")
        if self.priority is not None and self.priority not in ALLOWED_PRIORITIES:
            raise CaseDraftValidationError("invalid priority", field="priority")
        normalized_steps: list[TestStep] = []
        for i, step in enumerate(self.steps):
            ns = step.normalized()
            if not ns.action:
                raise CaseDraftValidationError("action must be non-empty", field=f"steps[{i}].action")
            if not ns.expected:
                raise CaseDraftValidationError("expected must be non-empty", field=f"steps[{i}].expected")
            normalized_steps.append(ns)
        self.title = self.title.strip()
        self.steps = normalized_steps
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/domain/case_draft/test_models.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/domain/case_draft tests/domain/case_draft
git commit -m "feat: add CaseDraft domain model and invariants"
```

---

### Task 3: Domain GenerationRun, Issue, status rules

**Files:**
- Create: `src/devspace_ai/domain/run/models.py`
- Create: `src/devspace_ai/domain/run/status.py`
- Create: `tests/domain/run/test_status.py`

**Interfaces:**
- Consumes: `CaseDraft`
- Produces:
  - `Issue(code: str, message: str, draft_index: int | None = None, field: str | None = None)`
  - `StepRecord(...)`, `RunTrace(steps: list[StepRecord])`
  - `RunStatus` enum: `RUNNING`, `SUCCEEDED`, `FAILED`, `PARTIAL`
  - `resolve_status(valid_count: int, issue_count: int) -> RunStatus`
  - `GenerationRun` dataclass with `mark_finished(status, drafts, issues)`

- [ ] **Step 1: Write failing tests**

```python
# tests/domain/run/test_status.py
from devspace_ai.domain.run.status import resolve_status
from devspace_ai.domain.run.models import RunStatus


def test_status_rules():
    assert resolve_status(valid_count=3, issue_count=0) == RunStatus.SUCCEEDED
    assert resolve_status(valid_count=2, issue_count=1) == RunStatus.PARTIAL
    assert resolve_status(valid_count=0, issue_count=1) == RunStatus.FAILED
    assert resolve_status(valid_count=0, issue_count=0) == RunStatus.FAILED
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/domain/run/test_status.py -v`

- [ ] **Step 3: Implement**

```python
# src/devspace_ai/domain/run/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from devspace_ai.domain.case_draft.models import CaseDraft


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class Issue:
    code: str
    message: str
    draft_index: int | None = None
    field: str | None = None


@dataclass
class StepRecord:
    step_name: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None
    error: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass
class RunTrace:
    steps: list[StepRecord] = field(default_factory=list)


@dataclass
class GenerationRun:
    run_id: str
    status: RunStatus
    input_text: str
    drafts: list[CaseDraft] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    trace: RunTrace = field(default_factory=RunTrace)
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def start(input_text: str) -> "GenerationRun":
        return GenerationRun(run_id=str(uuid4()), status=RunStatus.RUNNING, input_text=input_text)

    def finish(self, status: RunStatus, drafts: list[CaseDraft], issues: list[Issue]) -> None:
        self.status = status
        self.drafts = drafts
        self.issues = issues
        self.error = issues[0].message if issues and status in (RunStatus.FAILED, RunStatus.PARTIAL) else None


# src/devspace_ai/domain/run/status.py
from .models import RunStatus


def resolve_status(valid_count: int, issue_count: int) -> RunStatus:
    if valid_count <= 0:
        return RunStatus.FAILED
    if issue_count > 0:
        return RunStatus.PARTIAL
    return RunStatus.SUCCEEDED
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/domain/run/test_status.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/domain/run tests/domain/run
git commit -m "feat: add GenerationRun model and status resolution"
```

---

### Task 4: Ingest validation (text/file limits) + requirement model

**Files:**
- Create: `src/devspace_ai/domain/requirement/models.py`
- Create: `src/devspace_ai/application/case_generation/errors.py`
- Create: `src/devspace_ai/infrastructure/source/text_ingest.py`
- Create: `tests/infrastructure/source/test_text_ingest.py`

**Interfaces:**
- Consumes: `Settings` limits
- Produces:
  - `RequirementDocument(source_type, title, text, metadata)`
  - `ingest_text(text, *, max_chars) -> RequirementDocument`
  - `ingest_upload(filename, raw_bytes, *, max_bytes, max_chars) -> RequirementDocument`
  - Raises `InputRejectedError(code, message)` for `INVALID_INPUT`, `INPUT_TOO_LONG`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`

- [ ] **Step 1: Write failing tests**

```python
# tests/infrastructure/source/test_text_ingest.py
import pytest
from devspace_ai.infrastructure.source.text_ingest import ingest_text, ingest_upload
from devspace_ai.application.case_generation.errors import InputRejectedError


def test_reject_empty_text():
    with pytest.raises(InputRejectedError) as ei:
        ingest_text("  ", max_chars=100)
    assert ei.value.code == "INVALID_INPUT"


def test_reject_too_long():
    with pytest.raises(InputRejectedError) as ei:
        ingest_text("a" * 11, max_chars=10)
    assert ei.value.code == "INPUT_TOO_LONG"
    assert "10" in ei.value.message


def test_reject_bad_extension_and_size():
    with pytest.raises(InputRejectedError) as ei:
        ingest_upload("a.pdf", b"x", max_bytes=10, max_chars=100)
    assert ei.value.code == "UNSUPPORTED_FILE_TYPE"
    with pytest.raises(InputRejectedError) as ei:
        ingest_upload("a.txt", b"01234567890", max_bytes=10, max_chars=100)
    assert ei.value.code == "FILE_TOO_LARGE"


def test_accept_md():
    doc = ingest_upload("req.md", b"# hello", max_bytes=100, max_chars=100)
    assert doc.text == "# hello"
    assert doc.source_type == "upload"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/infrastructure/source/test_text_ingest.py -v`

- [ ] **Step 3: Implement**

```python
# src/devspace_ai/application/case_generation/errors.py
class InputRejectedError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# src/devspace_ai/domain/requirement/models.py
from dataclasses import dataclass, field


@dataclass
class RequirementDocument:
    source_type: str  # paste | upload
    text: str
    title: str | None = None
    metadata: dict = field(default_factory=dict)


# src/devspace_ai/infrastructure/source/text_ingest.py
from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.domain.requirement.models import RequirementDocument

ALLOWED_SUFFIXES = {".txt", ".md"}


def ingest_text(text: str, *, max_chars: int) -> RequirementDocument:
    if text is None or not str(text).strip():
        raise InputRejectedError("INVALID_INPUT", "text must be non-empty when provided")
    normalized = str(text)
    if len(normalized) > max_chars:
        raise InputRejectedError(
            "INPUT_TOO_LONG",
            f"text length {len(normalized)} exceeds limit {max_chars}",
        )
    return RequirementDocument(source_type="paste", text=normalized, metadata={"chars": len(normalized)})


def ingest_upload(filename: str, raw: bytes, *, max_bytes: int, max_chars: int) -> RequirementDocument:
    name = filename or ""
    lower = name.lower()
    if not any(lower.endswith(suf) for suf in ALLOWED_SUFFIXES):
        raise InputRejectedError(
            "UNSUPPORTED_FILE_TYPE",
            "only .txt and .md uploads are supported",
        )
    if len(raw) > max_bytes:
        raise InputRejectedError(
            "FILE_TOO_LARGE",
            f"file size {len(raw)} bytes exceeds limit {max_bytes} bytes",
        )
    text = raw.decode("utf-8", errors="replace")
    doc = ingest_text(text, max_chars=max_chars)
    doc.source_type = "upload"
    doc.title = name
    doc.metadata.update({"filename": name, "bytes": len(raw)})
    return doc
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/infrastructure/source/test_text_ingest.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/domain/requirement src/devspace_ai/application/case_generation/errors.py src/devspace_ai/infrastructure/source tests/infrastructure/source
git commit -m "feat: add requirement ingest with explicit rejection errors"
```

---

### Task 5: Fake Model + ModelPort + prompt parsing

**Files:**
- Create: `src/devspace_ai/application/port/outbound/model_port.py`
- Create: `src/devspace_ai/infrastructure/prompt/case_generation.py`
- Create: `src/devspace_ai/infrastructure/model/fake_model.py`
- Create: `src/devspace_ai/infrastructure/model/factory.py`
- Create: `tests/infrastructure/model/test_fake_model.py`

**Interfaces:**
- Consumes: `RequirementDocument`, settings
- Produces:
  - `ModelPort.generate_case_drafts(requirement_text, *, max_cases, language, domain_hint, repair_issues: list[str] | None) -> ModelGenerationResult`
  - `ModelGenerationResult(raw_drafts: list[dict], prompt_tokens, completion_tokens, model)`
  - `FakeModelAdapter` deterministic 2–3 drafts; at least one `test_data=null` and one non-null
  - `build_model_adapter(settings) -> ModelPort` chooses fake when `model_provider==fake` or api key missing

- [ ] **Step 1: Write failing tests**

```python
# tests/infrastructure/model/test_fake_model.py
import asyncio
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.factory import build_model_adapter


def test_fake_returns_structured_drafts():
    adapter = FakeModelAdapter()
    result = asyncio.get_event_loop().run_until_complete(
        adapter.generate_case_drafts("登录需求", max_cases=10, language="zh-CN", domain_hint=None, repair_issues=None)
    )
    assert 2 <= len(result.raw_drafts) <= 3
    datas = [s.get("test_data") for d in result.raw_drafts for s in d["steps"]]
    assert None in datas
    assert any(x for x in datas if x)


def test_factory_defaults_to_fake_without_key():
    s = Settings(_env_file=None, model_api_key=None, model_provider=None)
    assert isinstance(build_model_adapter(s), FakeModelAdapter)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/infrastructure/model/test_fake_model.py -v`

- [ ] **Step 3: Implement port + fake + factory**

```python
# src/devspace_ai/application/port/outbound/model_port.py
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelGenerationResult:
    raw_drafts: list[dict]
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ModelPort(Protocol):
    async def generate_case_drafts(
        self,
        requirement_text: str,
        *,
        max_cases: int,
        language: str,
        domain_hint: str | None,
        repair_issues: list[str] | None,
    ) -> ModelGenerationResult: ...


# src/devspace_ai/infrastructure/model/fake_model.py
from devspace_ai.application.port.outbound.model_port import ModelGenerationResult


class FakeModelAdapter:
    async def generate_case_drafts(self, requirement_text, *, max_cases, language, domain_hint, repair_issues):
        drafts = [
            {
                "title": "主路径验证",
                "preconditions": ["系统可用"],
                "steps": [
                    {"action": "打开功能入口", "expected": "页面加载成功", "test_data": None},
                    {"action": "提交合法数据", "expected": "操作成功", "test_data": "user=demo"},
                ],
                "priority": "P1",
                "tags": ["fake"],
                "rationale": f"based on:{requirement_text[:32]}",
            },
            {
                "title": "异常路径验证",
                "preconditions": [],
                "steps": [{"action": "提交空数据", "expected": "提示校验错误", "test_data": None}],
                "priority": "P2",
                "tags": ["fake", "negative"],
                "rationale": "cover invalid input",
            },
        ]
        return ModelGenerationResult(raw_drafts=drafts[:max_cases], model="fake", prompt_tokens=0, completion_tokens=0)


# src/devspace_ai/infrastructure/model/factory.py
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter


def build_model_adapter(settings: Settings):
    provider = settings.model_provider
    if provider == "fake" or not settings.model_api_key:
        return FakeModelAdapter()
    from devspace_ai.infrastructure.model.openai_compatible import OpenAICompatibleModelAdapter
    return OpenAICompatibleModelAdapter(settings)
```

Add a minimal prompt helper module (string builder) used later by the OpenAI adapter:

```python
# src/devspace_ai/infrastructure/prompt/case_generation.py
import json

SCHEMA_HINT = {
    "drafts": [
        {
            "title": "string",
            "preconditions": ["string"],
            "steps": [{"action": "string", "expected": "string", "test_data": "string|null"}],
            "priority": "P0|P1|P2|P3|null",
            "tags": ["string"],
            "rationale": "string|null",
        }
    ]
}


def build_messages(requirement_text: str, *, max_cases: int, language: str, domain_hint: str | None, repair_issues: list[str] | None) -> list[dict]:
    system = (
        "You generate manual test case drafts as JSON only. "
        f"Language={language}. Return at most {max_cases} drafts. "
        "Each step needs action, expected, test_data (null if no concrete data). "
        f"Schema: {json.dumps(SCHEMA_HINT, ensure_ascii=False)}"
    )
    user = requirement_text if not domain_hint else f"{requirement_text}\n\nDomain hint:\n{domain_hint}"
    if repair_issues:
        user += "\n\nFix these validation issues and return full JSON again:\n- " + "\n- ".join(repair_issues)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/infrastructure/model/test_fake_model.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/application/port src/devspace_ai/infrastructure/model src/devspace_ai/infrastructure/prompt tests/infrastructure/model
git commit -m "feat: add ModelPort and deterministic Fake Model"
```

---

### Task 6: OpenAI-compatible adapter + SQLite run repository

**Files:**
- Create: `src/devspace_ai/infrastructure/model/openai_compatible.py`
- Create: `src/devspace_ai/application/port/outbound/run_repository_port.py`
- Create: `src/devspace_ai/infrastructure/persistence/sqlite_run_repository.py`
- Create: `tests/infrastructure/model/test_openai_compatible.py`
- Create: `tests/infrastructure/persistence/test_sqlite_run_repository.py`

**Interfaces:**
- Consumes: `Settings`, `GenerationRun`
- Produces:
  - `OpenAICompatibleModelAdapter` calling `POST {base}/chat/completions` with JSON schema-ish prompt; parse `drafts` array from message content
  - `RunRepositoryPort.save(run)`, `get(run_id)`, `list_recent(limit=20)`
  - SQLite JSON serialization of drafts/issues/trace

- [ ] **Step 1: Write failing repository test**

```python
# tests/infrastructure/persistence/test_sqlite_run_repository.py
from pathlib import Path
from devspace_ai.domain.run.models import GenerationRun, RunStatus, Issue
from devspace_ai.infrastructure.persistence.sqlite_run_repository import SqliteRunRepository


def test_save_and_get(tmp_path: Path):
    repo = SqliteRunRepository(tmp_path / "runs.db")
    run = GenerationRun.start("req")
    run.finish(RunStatus.FAILED, [], [Issue(code="NO_VALID_DRAFTS", message="none")])
    repo.save(run)
    loaded = repo.get(run.run_id)
    assert loaded is not None
    assert loaded.status == RunStatus.FAILED
    assert loaded.issues[0].code == "NO_VALID_DRAFTS"
```

- [ ] **Step 2: Implement SQLite repository**

```python
# src/devspace_ai/application/port/outbound/run_repository_port.py
from typing import Protocol
from devspace_ai.domain.run.models import GenerationRun


class RunRepositoryPort(Protocol):
    def save(self, run: GenerationRun) -> None: ...
    def get(self, run_id: str) -> GenerationRun | None: ...
    def list_recent(self, limit: int = 20) -> list[GenerationRun]: ...


# src/devspace_ai/infrastructure/persistence/sqlite_run_repository.py
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.run.models import GenerationRun, Issue, RunStatus, RunTrace, StepRecord


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    raise TypeError(type(obj))


class SqliteRunRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    def save(self, run: GenerationRun) -> None:
        payload = json.dumps(asdict(run), ensure_ascii=False, default=_json_default)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO runs(run_id, payload_json, created_at) VALUES (?, ?, ?)",
                (run.run_id, payload, run.created_at.isoformat()),
            )

    def get(self, run_id: str) -> GenerationRun | None:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._from_json(row[0]) if row else None

    def list_recent(self, limit: int = 20) -> list[GenerationRun]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                "SELECT payload_json FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._from_json(r[0]) for r in rows]

    def _from_json(self, payload: str) -> GenerationRun:
        data = json.loads(payload)
        drafts = [
            CaseDraft(
                title=d["title"],
                preconditions=d.get("preconditions") or [],
                steps=[TestStep(**s) for s in d.get("steps") or []],
                priority=d.get("priority"),
                tags=d.get("tags") or [],
                rationale=d.get("rationale"),
            )
            for d in data.get("drafts") or []
        ]
        issues = [Issue(**i) for i in data.get("issues") or []]
        steps = []
        for s in (data.get("trace") or {}).get("steps") or []:
            steps.append(
                StepRecord(
                    step_name=s["step_name"],
                    status=s["status"],
                    started_at=datetime.fromisoformat(s["started_at"]),
                    ended_at=datetime.fromisoformat(s["ended_at"]) if s.get("ended_at") else None,
                    summary=s.get("summary"),
                    error=s.get("error"),
                    prompt_tokens=s.get("prompt_tokens"),
                    completion_tokens=s.get("completion_tokens"),
                )
            )
        return GenerationRun(
            run_id=data["run_id"],
            status=RunStatus(data["status"]),
            input_text=data["input_text"],
            drafts=drafts,
            issues=issues,
            trace=RunTrace(steps=steps),
            error=data.get("error"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
```

- [ ] **Step 3: Write OpenAI adapter test with httpx MockTransport**

```python
# tests/infrastructure/model/test_openai_compatible.py
import json
import httpx
import pytest
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.openai_compatible import OpenAICompatibleModelAdapter


@pytest.mark.asyncio
async def test_parses_drafts_from_chat_completion():
    payload = {
        "choices": [{"message": {"content": json.dumps({"drafts": [{"title": "t", "preconditions": [], "steps": [{"action": "a", "expected": "e", "test_data": None}], "priority": None, "tags": [], "rationale": None}]})}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        "model": "demo",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    settings = Settings(_env_file=None, model_base_url="https://example.com/v1", model_api_key="k", model_name="demo")
    adapter = OpenAICompatibleModelAdapter(settings, transport=transport)
    result = await adapter.generate_case_drafts("req", max_cases=10, language="zh-CN", domain_hint=None, repair_issues=None)
    assert result.raw_drafts[0]["title"] == "t"
    assert result.prompt_tokens == 1
```

```python
# src/devspace_ai/infrastructure/model/openai_compatible.py
import json
import httpx
from devspace_ai.application.port.outbound.model_port import ModelGenerationResult
from devspace_ai.infrastructure.prompt.case_generation import build_messages


class OpenAICompatibleModelAdapter:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    async def generate_case_drafts(self, requirement_text, *, max_cases, language, domain_hint, repair_issues):
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
        headers = {"Authorization": f"Bearer {self.settings.model_api_key}", "Content-Type": "application/json"}
        body = {
            "model": self.settings.model_name,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds, transport=self.transport) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
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
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/infrastructure/persistence/test_sqlite_run_repository.py tests/infrastructure/model/test_openai_compatible.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/infrastructure/persistence src/devspace_ai/infrastructure/model/openai_compatible.py src/devspace_ai/application/port/outbound/run_repository_port.py tests/infrastructure
git commit -m "feat: add OpenAI-compatible model adapter and SQLite run repository"
```

---

### Task 7: Application Graph service (ingest → generate → validate → persist)

**Files:**
- Create: `src/devspace_ai/application/dto/commands.py`
- Create: `src/devspace_ai/application/dto/results.py`
- Create: `src/devspace_ai/application/port/inbound/generate_case_drafts_port.py`
- Create: `src/devspace_ai/application/case_generation/service.py`
- Create: `tests/application/case_generation/test_service.py`

**Interfaces:**
- Consumes: `ModelPort`, `RunRepositoryPort`, `Settings`, ingest helpers, domain validators, `resolve_status`
- Produces: `CaseGenerationService.generate(command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult`
- Command fields: `text: str | None`, `file_name: str | None`, `file_bytes: bytes | None`, `language`, `max_cases: int | None`, `domain_hint`
- Exactly one of text/file; enforce hard max cases; one validation repair retry; map raw dicts → `CaseDraft`; persist always before return (including timeout/failure)

- [ ] **Step 1: Write failing application tests with fake ports**

```python
# tests/application/case_generation/test_service.py
import asyncio
import pytest
from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.case_generation.service import CaseGenerationService
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.port.outbound.model_port import ModelGenerationResult
from devspace_ai.domain.run.models import GenerationRun, RunStatus
from devspace_ai.infrastructure.config.settings import Settings
from devspace_ai.infrastructure.model.fake_model import FakeModelAdapter


class InMemoryRunRepository:
    def __init__(self):
        self.store: dict[str, GenerationRun] = {}

    def save(self, run: GenerationRun) -> None:
        self.store[run.run_id] = run

    def get(self, run_id: str):
        return self.store.get(run_id)

    def list_recent(self, limit: int = 20):
        return list(self.store.values())[:limit]


@pytest.mark.asyncio
async def test_happy_path_succeeded():
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(settings=Settings(_env_file=None), model=FakeModelAdapter(), runs=repo)
    result = await svc.generate(GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None))
    assert result.status == RunStatus.SUCCEEDED
    assert len(result.drafts) >= 2
    assert repo.get(result.run_id) is not None


@pytest.mark.asyncio
async def test_max_cases_hard_limit():
    svc = CaseGenerationService(settings=Settings(_env_file=None), model=FakeModelAdapter(), runs=InMemoryRunRepository())
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(GenerateCaseDraftsCommand(text="x", file_name=None, file_bytes=None, max_cases=31))
    assert ei.value.code == "MAX_CASES_EXCEEDED"


@pytest.mark.asyncio
async def test_xor_input():
    svc = CaseGenerationService(settings=Settings(_env_file=None), model=FakeModelAdapter(), runs=InMemoryRunRepository())
    with pytest.raises(InputRejectedError) as ei:
        await svc.generate(GenerateCaseDraftsCommand(text="x", file_name="a.txt", file_bytes=b"x"))
    assert ei.value.code == "INVALID_INPUT"


class TimeoutModel:
    async def generate_case_drafts(self, *args, **kwargs):
        raise TimeoutError("model timed out")


@pytest.mark.asyncio
async def test_model_timeout_persists_failed_run():
    repo = InMemoryRunRepository()
    svc = CaseGenerationService(settings=Settings(_env_file=None), model=TimeoutModel(), runs=repo)
    result = await svc.generate(GenerateCaseDraftsCommand(text="用户登录", file_name=None, file_bytes=None))
    assert result.status == RunStatus.FAILED
    assert result.issues[0].code == "MODEL_TIMEOUT"
    assert repo.get(result.run_id) is not None
```

- [ ] **Step 2: Implement DTOs + service**

```python
# src/devspace_ai/application/dto/commands.py
from dataclasses import dataclass


@dataclass
class GenerateCaseDraftsCommand:
    text: str | None
    file_name: str | None
    file_bytes: bytes | None
    language: str = "zh-CN"
    max_cases: int | None = None
    domain_hint: str | None = None


# src/devspace_ai/application/dto/results.py
from dataclasses import dataclass
from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.run.models import Issue, RunStatus, RunTrace


@dataclass
class GenerateCaseDraftsResult:
    run_id: str
    status: RunStatus
    drafts: list[CaseDraft]
    issues: list[Issue]
    trace: RunTrace
    error: str | None


# src/devspace_ai/application/case_generation/service.py
import asyncio
from datetime import datetime, timezone
from devspace_ai.application.case_generation.errors import InputRejectedError
from devspace_ai.application.dto.commands import GenerateCaseDraftsCommand
from devspace_ai.application.dto.results import GenerateCaseDraftsResult
from devspace_ai.domain.case_draft.errors import CaseDraftValidationError
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.run.models import GenerationRun, Issue, RunStatus, StepRecord
from devspace_ai.domain.run.status import resolve_status
from devspace_ai.infrastructure.source.text_ingest import ingest_text, ingest_upload


class CaseGenerationService:
    def __init__(self, settings, model, runs):
        self.settings = settings
        self.model = model
        self.runs = runs

    async def generate(self, command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult:
        has_text = command.text is not None and str(command.text).strip() != ""
        has_file = command.file_bytes is not None
        if has_text == has_file:
            raise InputRejectedError("INVALID_INPUT", "provide exactly one of text or file")

        max_cases = self.settings.default_max_cases if command.max_cases is None else command.max_cases
        if max_cases > self.settings.hard_max_cases:
            raise InputRejectedError(
                "MAX_CASES_EXCEEDED",
                f"max_cases {max_cases} exceeds hard limit {self.settings.hard_max_cases}",
            )
        if max_cases < 1:
            raise InputRejectedError("INVALID_INPUT", "max_cases must be >= 1")

        if has_file:
            doc = ingest_upload(
                command.file_name or "upload.txt",
                command.file_bytes or b"",
                max_bytes=self.settings.max_upload_bytes,
                max_chars=self.settings.max_text_chars,
            )
        else:
            doc = ingest_text(command.text or "", max_chars=self.settings.max_text_chars)

        run = GenerationRun.start(doc.text)
        t0 = datetime.now(timezone.utc)
        run.trace.steps.append(StepRecord("ingest_requirement", "succeeded", t0, datetime.now(timezone.utc), summary=f"chars={len(doc.text)}"))

        try:
            drafts, issues = await asyncio.wait_for(
                self._generate_and_validate(doc.text, max_cases, command.language, command.domain_hint, run),
                timeout=self.settings.total_timeout_seconds,
            )
            status = resolve_status(len(drafts), len(issues))
            run.finish(status, drafts, issues)
        except TimeoutError:
            run.finish(RunStatus.FAILED, [], [Issue("MODEL_TIMEOUT", "model or total request timed out")])
            run.trace.steps.append(
                StepRecord("generate_cases", "failed", datetime.now(timezone.utc), datetime.now(timezone.utc), error="timeout")
            )
        self.runs.save(run)
        return GenerateCaseDraftsResult(run.run_id, run.status, run.drafts, run.issues, run.trace, run.error)

    async def _generate_and_validate(self, text, max_cases, language, domain_hint, run):
        started = datetime.now(timezone.utc)
        raw = await self.model.generate_case_drafts(
            text, max_cases=max_cases, language=language, domain_hint=domain_hint, repair_issues=None
        )
        drafts, issues = self._validate_raw(raw.raw_drafts)
        run.trace.steps.append(
            StepRecord(
                "generate_cases",
                "succeeded",
                started,
                datetime.now(timezone.utc),
                summary=f"raw={len(raw.raw_drafts)}",
                prompt_tokens=raw.prompt_tokens,
                completion_tokens=raw.completion_tokens,
            )
        )
        if issues:
            started = datetime.now(timezone.utc)
            raw = await self.model.generate_case_drafts(
                text,
                max_cases=max_cases,
                language=language,
                domain_hint=domain_hint,
                repair_issues=[i.message for i in issues],
            )
            drafts, issues = self._validate_raw(raw.raw_drafts)
            run.trace.steps.append(
                StepRecord("validate_cases", "succeeded", started, datetime.now(timezone.utc), summary=f"retry valid={len(drafts)} issues={len(issues)}")
            )
        else:
            run.trace.steps.append(
                StepRecord("validate_cases", "succeeded", datetime.now(timezone.utc), datetime.now(timezone.utc), summary="ok")
            )
        return drafts, issues

    def _validate_raw(self, raw_drafts: list[dict]):
        valid = []
        issues: list[Issue] = []
        for idx, item in enumerate(raw_drafts or []):
            try:
                steps = [
                    TestStep(
                        action=str(s.get("action", "")),
                        expected=str(s.get("expected", "")),
                        test_data=s.get("test_data"),
                    )
                    for s in (item.get("steps") or [])
                ]
                draft = CaseDraft(
                    title=str(item.get("title", "")),
                    preconditions=[str(x) for x in (item.get("preconditions") or [])],
                    steps=steps,
                    priority=item.get("priority"),
                    tags=[str(x) for x in (item.get("tags") or [])],
                    rationale=item.get("rationale"),
                )
                draft.validate()
                valid.append(draft)
            except (CaseDraftValidationError, TypeError, ValueError) as exc:
                field = getattr(exc, "field", None)
                issues.append(Issue("DRAFT_VALIDATION_FAILED", str(exc), draft_index=idx, field=field))
        if not valid and not issues:
            issues.append(Issue("NO_VALID_DRAFTS", "model returned no drafts"))
        return valid, issues
```

- [ ] **Step 3: Run — expect PASS**

Run: `pytest tests/application/case_generation/test_service.py -v`

- [ ] **Step 4: Commit**

```bash
git add src/devspace_ai/application tests/application
git commit -m "feat: implement case generation graph service"
```

---

### Task 8: REST API (multipart generate + get run)

**Files:**
- Create: `src/devspace_ai/interfaces/rest/schemas.py`
- Create: `src/devspace_ai/interfaces/rest/errors.py`
- Create: `src/devspace_ai/interfaces/rest/routes_case_drafts.py`
- Modify: `src/devspace_ai/apps/api/main.py` (wire routes + DI)
- Create: `tests/interfaces/rest/test_case_drafts_api.py`

**Interfaces:**
- Consumes: `CaseGenerationService`
- Produces:
  - `POST /api/v1/case-drafts/generate` multipart
  - `GET /api/v1/runs/{run_id}`
  - 400 body: `{"issues":[{"code","message",...}]}`
  - 200 body: run DTO with drafts/trace/issues/status

- [ ] **Step 1: Write API tests with TestClient + Fake model wiring**

Tests:
1. paste text → 200 succeeded/partial with drafts
2. missing both fields → 400 `INVALID_INPUT`
3. too long text → 400 `INPUT_TOO_LONG` message contains limit
4. get run by id after generate

- [ ] **Step 2: Implement routes + wire `create_app`**

In `create_app`:
- build settings, model adapter, sqlite repo (use tmp path in tests via dependency override or constructor arg)
- mount router

- [ ] **Step 3: Run — expect PASS**

Run: `pytest tests/interfaces/rest/test_case_drafts_api.py -v`

- [ ] **Step 4: Commit**

```bash
git add src/devspace_ai/interfaces/rest src/devspace_ai/apps/api/main.py tests/interfaces/rest
git commit -m "feat: expose synchronous case draft generation API"
```

---

### Task 9: Jinja debug UI

**Files:**
- Create: `src/devspace_ai/interfaces/web_debug/routes.py`
- Create: `src/devspace_ai/interfaces/web_debug/templates/base.html`
- Create: `src/devspace_ai/interfaces/web_debug/templates/index.html`
- Create: `src/devspace_ai/interfaces/web_debug/templates/run_detail.html`
- Modify: `src/devspace_ai/apps/api/main.py` (mount debug routes + Jinja templates)
- Create: `tests/interfaces/web_debug/test_debug_pages.py`

**Interfaces:**
- Consumes: same generate use case / REST internally (prefer calling application service from form POST, not duplicating logic)
- Produces:
  - `GET /debug/` form page
  - `POST /debug/generate` → render results + trace + issues + JSON copy block
  - `GET /debug/runs/{run_id}` replay

- [ ] **Step 1: Write failing page tests**

```python
def test_debug_get_form():
    client = TestClient(create_app(...))
    r = client.get("/debug/")
    assert r.status_code == 200
    assert "生成用例" in r.text


def test_debug_generate_paste():
    r = client.post("/debug/generate", data={"text": "用户可以登录系统", "language": "zh-CN"})
    assert r.status_code == 200
    assert "主路径" in r.text or "draft" in r.text.lower()
    assert "ingest" in r.text or "轨迹" in r.text
```

- [ ] **Step 2: Implement Jinja templates + routes**

Keep UI minimal: textarea, file input, max_cases, domain_hint, submit; results list steps including `test_data`; show issues; link to run detail.

- [ ] **Step 3: Run — expect PASS**

Run: `pytest tests/interfaces/web_debug/test_debug_pages.py -v`

- [ ] **Step 4: Commit**

```bash
git add src/devspace_ai/interfaces/web_debug tests/interfaces/web_debug src/devspace_ai/apps/api/main.py
git commit -m "feat: add Jinja debug UI for case draft generation"
```

---

### Task 10: README hardening + full test suite

**Files:**
- Create: `README.md`
- Modify: `.env.example` if needed
- Modify: any small gaps found while running full suite

**Interfaces:**
- Consumes: completed app
- Produces: documented runbook

- [ ] **Step 1: Write README with exact commands**

Include:
- `python -m pip install -e ".[dev]"`
- `uvicorn devspace_ai.apps.api.main:create_app --factory --reload`
- open `http://127.0.0.1:8000/debug/`
- configure `MODEL_BASE_URL` / `MODEL_API_KEY` / `MODEL_NAME`
- note Fake Model default without key
- link to design spec

- [ ] **Step 2: Run full suite**

Run: `pytest -v`  
Expected: all PASS without real model key

- [ ] **Step 3: Manual smoke (optional)**

Start server, paste a short requirement on `/debug/`, confirm drafts + trace.

- [ ] **Step 4: Commit**

```bash
git add README.md .env.example
git commit -m "docs: add README and finalize v1 runbook"
```

---

## Spec Coverage Check

| Spec item | Task |
| --- | --- |
| Light DDD package layout | 1–7 |
| CaseDraft + nullable `test_data` | 2 |
| Run status rules / issues | 3, 7 |
| Paste/upload ingest + reject limits | 4, 8 |
| Fake + OpenAI-compatible model | 5, 6 |
| Sync Graph orchestration + repair once | 7 |
| REST multipart + get run | 8 |
| Jinja debug UI | 9 |
| README / CI without key | 1, 5, 10 |
| No TMS write / no auth / no SPA | honored by omission |
| Alternatives/future capabilities | out of v1 scope (no tasks) |

## Placeholder / Consistency Notes

- Package import root is `devspace_ai` under `src/` (packaging adaptation of spec folders).
- Timeout: implement total timeout with `asyncio.wait_for` around model calls / generate loop; map `TimeoutError` → `MODEL_TIMEOUT`.
- HTTP 4xx for input rejection happens before Run creation; runtime failures return HTTP 200 with failed/partial Run (per DEC-015/016 table).
