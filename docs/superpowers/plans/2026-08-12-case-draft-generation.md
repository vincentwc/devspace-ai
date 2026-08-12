# 用例草稿生成（Case Draft Generation）实现计划

> **面向执行代理：** 必选子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐步实现。步骤使用 checkbox（`- [ ]`）跟踪。

**目标：** 在 `devspace-ai` 落地 v1：通过 Jinja 调试页，将粘贴/上传的需求文本同步生成为通过校验的 `CaseDraft[]`，并展示 Run 轨迹；内部采用可演进的瘦 Agent Graph，模型支持 Fake / OpenAI 兼容协议。

**架构：** 轻量 DDD + 六边形（Ports & Adapters）。应用层编排固定 Graph：`ingest → generate → validate → persist`。领域层拥有 `CaseDraft` / `GenerationRun` 不变量。基础设施提供 Fake/OpenAI 模型、multipart 摄入、SQLite Run 存储。接口层提供 REST + Jinja 调试页，共用同一应用用例。

**规格依据：** `docs/superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md`

**文档语言：** 本计划正文、任务说明、验收预期一律使用中文；代码标识符、API 路径、错误码保持英文（业界惯例）。

---

## 1. 技术架构基线（生产向）

### 1.1 运行与分层

```text
                    ┌─────────────────────────────┐
                    │  Jinja 调试页 / 外部 TMS     │
                    └──────────────┬──────────────┘
                                   │ HTTP / multipart
                    ┌──────────────▼──────────────┐
                    │ interfaces（REST + web_debug）│
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │ application（Graph 编排）     │
                    │  ports: inbound / outbound   │
                    └──────┬───────────────┬──────┘
                           │               │
              ┌────────────▼───┐     ┌─────▼────────────┐
              │ domain         │     │ infrastructure   │
              │ CaseDraft/Run  │     │ model/source/db  │
              └────────────────┘     └──────────────────┘
```

| 层级 | 职责 | 禁止 |
| --- | --- | --- |
| `interfaces` | HTTP DTO、路由、Jinja、错误映射 | 业务规则、直连 DB/模型 SDK 细节 |
| `application` | 用例编排、事务/超时边界、端口调用 | FastAPI/SQL/httpx 细节 |
| `domain` | 不变量、状态机、纯领域对象 | 框架、IO、提示词 |
| `infrastructure` | 模型客户端、SQLite、文件解析、配置、日志 | 被 domain 反向依赖 |
| `apps/api` | 组装根（DI）、进程入口 | 堆业务逻辑 |

依赖方向：`interfaces → application → domain`；`infrastructure → application.port / domain`。

### 1.2 工程与工具链（锁定）

| 类别 | 选型 | 版本（2026-08-12 锁定） | 说明 |
| --- | --- | --- | --- |
| 语言 | Python | **3.12.x**（`requires-python = ">=3.12,<3.14"`） | 生产常用 LTS 线；本地与 CI 一致 |
| 包管理 | **uv** | `0.12.3` | 安装依赖 + 生成锁文件 |
| Web | FastAPI | `0.141.1` | ASGI API |
| 服务器 | uvicorn[standard] | `0.52.1` | 生产/本地均用 |
| 校验/配置 | pydantic / pydantic-settings | `2.13.4` / `2.15.0` | Settings 与 DTO |
| HTTP 客户端 | httpx | `0.28.1` | 模型调用 + TestClient |
| 模板 | Jinja2 | `3.1.6` | 调试页 |
| 上传 | python-multipart | `0.0.32` | multipart 解析 |
| 持久化 | SQLite（stdlib） | 随 Python | v1 Run 存储；路径可配置 |
| 测试 | pytest / pytest-asyncio | `9.1.1` / `1.4.0` | 默认 CI |
| Lint | ruff | `0.16.2` | format + lint |
| 类型检查 | mypy | `2.3.0`（`strict = true`） | 见 Task 1 配置 |
| 容器 | Docker（python:3.12-slim） | 官方 slim | 多阶段构建 |
| CI | GitHub Actions | `ubuntu-latest` + Python 3.12 | lint/type/test |

> **锁文件策略：** `pyproject.toml` 写精确主依赖版本；用 `uv lock` 生成 `uv.lock` 并提交仓库。应用/CI 一律 `uv sync --frozen`。

> **不引入：** LangChain / LlamaIndex / 重型 Agent 框架；v1 不用 PostgreSQL、不用 Redis、不做鉴权网关。

### 1.3 推荐仓库布局

```text
devspace-ai/
├── pyproject.toml
├── uv.lock
├── .python-version                 # 3.12
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml              # 本地一键
├── Makefile                        # lint/test/run 快捷入口
├── README.md
├── docs/
│   ├── architecture.md             # 架构说明（中文）
│   └── superpowers/
│       ├── specs/...
│       └── plans/...
├── .github/workflows/ci.yml
├── src/devspace_ai/
│   ├── apps/api/main.py
│   ├── interfaces/{rest,web_debug}/
│   ├── application/...
│   ├── domain/...
│   └── infrastructure/...
└── tests/                          # 镜像 src 结构
```

### 1.4 运行时配置（环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | `local` / `test` / `prod` |
| `LOG_LEVEL` | `INFO` | 结构化日志级别 |
| `MODEL_BASE_URL` | 空 | OpenAI 兼容网关 |
| `MODEL_API_KEY` | 空 | 密钥；空则 Fake |
| `MODEL_NAME` | `gpt-4o-mini` | 模型名 |
| `MODEL_PROVIDER` | 空（自动） | `openai_compatible` / `fake` |
| `MAX_TEXT_CHARS` | `50000` | 超长拒绝 |
| `MAX_UPLOAD_BYTES` | `1048576` | 超大拒绝 |
| `DEFAULT_MAX_CASES` | `10` | |
| `HARD_MAX_CASES` | `30` | |
| `MODEL_TIMEOUT_SECONDS` | `120` | |
| `TOTAL_TIMEOUT_SECONDS` | `150` | |
| `SQLITE_PATH` | `data/runs.db` | |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | |

密钥不得入库；生产通过环境/密钥管理注入。

### 1.5 可观测与质量门禁

- 日志：stdlib `logging` + JSON 格式（`run_id` 关联）；默认不打印完整提示词。
- 健康检查：`GET /health`（存活）、`GET /ready`（可读写 SQLite）。
- CI 门禁：`ruff check` + `ruff format --check` + `mypy` + `pytest`；无真实模型密钥必须全绿。
- OpenAPI：由 FastAPI 自动生成，路径前缀 `/api/v1`。

---

## 2. 全局业务约束（摘自已确认规格）

- 同步 API：`POST /api/v1/case-drafts/generate` 阻塞至 Graph 结束或总超时。
- 对外状态：`running | succeeded | failed | partial`（不暴露 `queued`）。
- 状态规则：全通过 → `succeeded`；≥1 可用且有问题 → `partial`；0 可用 → `failed`。
- 超长文本 / 超大文件直接 4xx，错误信息含原因与上限。
- `max_cases` 默认 10，硬顶 30。
- 超时落库失败 Run，`issues` 含 `MODEL_TIMEOUT`。
- `issues[] = { code, message, draft_index?, field? }`。
- 不写 TMS；无鉴权；调试页 = Jinja + 少量 JS；禁止独立 SPA。
- 无密钥时确定性 Fake Model。

---

## 3. 文件职责图

| 路径 | 职责 |
| --- | --- |
| `pyproject.toml` / `uv.lock` | 依赖与工具配置 |
| `docs/architecture.md` | 架构说明（中文） |
| `Dockerfile` / `docker-compose.yml` / `Makefile` | 构建与本地交付 |
| `.github/workflows/ci.yml` | CI |
| `src/devspace_ai/domain/case_draft/*` | 用例草稿不变量 |
| `src/devspace_ai/domain/run/*` | Run / 轨迹 / 状态 |
| `src/devspace_ai/domain/requirement/*` | 需求文档模型 |
| `src/devspace_ai/application/case_generation/*` | Graph 编排 |
| `src/devspace_ai/application/port/*` | 入站/出站端口 |
| `src/devspace_ai/infrastructure/model/*` | Fake / OpenAI 兼容 |
| `src/devspace_ai/infrastructure/persistence/*` | SQLite |
| `src/devspace_ai/infrastructure/source/*` | 文本/文件摄入 |
| `src/devspace_ai/infrastructure/config/*` | Settings / 日志 |
| `src/devspace_ai/interfaces/rest/*` | REST |
| `src/devspace_ai/interfaces/web_debug/*` | 调试页 |
| `src/devspace_ai/apps/api/main.py` | 应用工厂与组装 |
| `tests/**` | 分层测试 |

---

### Task 1: 生产级工程脚手架（依赖锁定 / 配置 / 健康检查 / CI）

**文件：**
- 创建：`pyproject.toml`、`uv.lock`（由 uv 生成）、`.python-version`、`.env.example`
- 创建：`Makefile`、`Dockerfile`、`docker-compose.yml`、`.github/workflows/ci.yml`
- 创建：`docs/architecture.md`、`README.md`（初版）
- 创建：`src/devspace_ai/infrastructure/config/settings.py`
- 创建：`src/devspace_ai/infrastructure/config/logging.py`
- 创建：`src/devspace_ai/apps/api/main.py`
- 创建：`tests/infrastructure/config/test_settings.py`、`tests/apps/test_health.py`

**接口：**
- 消费：无
- 产出：`Settings`；`create_app() -> FastAPI`；`GET /health`、`GET /ready`；可 `make test` / `make lint`

- [ ] **步骤 1：编写失败的配置测试**

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

- [ ] **步骤 2：运行测试确认失败**

```bash
cd /Users/vincent/developEnv/code/ai/devspace-ai
# 若本机无 uv：curl -LsSf https://astral.sh/uv/install.sh | sh
uv python pin 3.12
# 先放最小 pyproject 后再 sync；此时应因模块不存在而失败
uv run pytest tests/infrastructure/config/test_settings.py -v
```

预期：FAIL（模块不存在）

- [ ] **步骤 3：落地 `pyproject.toml`（精确版本）与 Settings**

```toml
[project]
name = "devspace-ai"
version = "0.1.0"
description = "通用测试域 AI 能力服务"
readme = "README.md"
requires-python = ">=3.12,<3.14"
dependencies = [
  "fastapi==0.141.1",
  "uvicorn[standard]==0.52.1",
  "jinja2==3.1.6",
  "python-multipart==0.0.32",
  "pydantic==2.13.4",
  "pydantic-settings==2.15.0",
  "httpx==0.28.1",
]

[project.optional-dependencies]
dev = [
  "pytest==9.1.1",
  "pytest-asyncio==1.4.0",
  "ruff==0.16.2",
  "mypy==2.3.0",
]

[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["devspace_ai"]
mypy_path = "src"
```

```python
# src/devspace_ai/infrastructure/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    model_base_url: str | None = None
    model_api_key: str | None = None
    model_name: str = "gpt-4o-mini"
    model_provider: str | None = None

    max_text_chars: int = 50_000
    max_upload_bytes: int = 1_048_576
    default_max_cases: int = 10
    hard_max_cases: int = 30
    model_timeout_seconds: float = 120
    total_timeout_seconds: float = 150
    sqlite_path: str = "data/runs.db"
```

同步创建日志初始化、`create_app`（含 `/health` `/ready`）、`.env.example`、`docs/architecture.md`（可先摘抄本计划 §1）、`Makefile`、`Dockerfile`、`docker-compose.yml`、CI workflow。

`Makefile` 最少目标：`sync` / `lint` / `typecheck` / `test` / `run` / `docker-up`。

```bash
uv lock
uv sync --all-extras --frozen
```

- [ ] **步骤 4：健康检查测试并通过 Task 1 全部测试**

```python
# tests/apps/test_health.py
from fastapi.testclient import TestClient
from devspace_ai.apps.api.main import create_app


def test_health_and_ready(tmp_path):
    app = create_app()
    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
```

```bash
uv run pytest tests/infrastructure/config/test_settings.py tests/apps/test_health.py -v
uv run ruff check src tests
uv run mypy
```

预期：全部通过（mypy 可随包逐步收紧，但 Task 1 至少 settings/main 无错误）。

- [ ] **步骤 5：提交**

```bash
git add pyproject.toml uv.lock .python-version .env.example Makefile Dockerfile docker-compose.yml \
  .github/workflows/ci.yml docs/architecture.md README.md src/devspace_ai tests
git commit -m "chore: 初始化生产级工程脚手架与依赖锁定"
```

---

### Task 2: 领域模型 CaseDraft / TestStep

**文件：**
- 创建：`src/devspace_ai/domain/case_draft/errors.py`
- 创建：`src/devspace_ai/domain/case_draft/models.py`
- 创建：`tests/domain/case_draft/test_models.py`

**接口：**
- 产出：`TestStep`、`CaseDraft`、`validate()`、`test_data` 空串规范为 `null`

- [ ] **步骤 1：编写失败测试**

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
        CaseDraft(
            title=" ",
            preconditions=[],
            steps=[TestStep("a", "b", None)],
            priority=None,
            tags=[],
            rationale=None,
        ).validate()
    with pytest.raises(CaseDraftValidationError):
        CaseDraft(title="t", preconditions=[], steps=[], priority=None, tags=[], rationale=None).validate()
```

- [ ] **步骤 2：运行确认失败** — `uv run pytest tests/domain/case_draft/test_models.py -v`

- [ ] **步骤 3：实现领域模型**

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

- [ ] **步骤 4：运行确认通过** — `uv run pytest tests/domain/case_draft/test_models.py -v`

- [ ] **步骤 5：提交** — `git commit -m "feat: 新增 CaseDraft 领域模型与不变量"`

---

### Task 3: GenerationRun、Issue 与状态判定

**文件：**
- 创建：`src/devspace_ai/domain/run/models.py`、`status.py`
- 创建：`tests/domain/run/test_status.py`

**接口：**
- 产出：`RunStatus`、`Issue`、`StepRecord`、`RunTrace`、`GenerationRun`、`resolve_status(valid_count, issue_count)`

- [ ] **步骤 1：编写失败测试**

```python
from devspace_ai.domain.run.status import resolve_status
from devspace_ai.domain.run.models import RunStatus


def test_status_rules():
    assert resolve_status(valid_count=3, issue_count=0) == RunStatus.SUCCEEDED
    assert resolve_status(valid_count=2, issue_count=1) == RunStatus.PARTIAL
    assert resolve_status(valid_count=0, issue_count=1) == RunStatus.FAILED
    assert resolve_status(valid_count=0, issue_count=0) == RunStatus.FAILED
```

- [ ] **步骤 2：运行确认失败**

- [ ] **步骤 3：实现**

```python
# src/devspace_ai/domain/run/status.py
from .models import RunStatus


def resolve_status(valid_count: int, issue_count: int) -> RunStatus:
    if valid_count <= 0:
        return RunStatus.FAILED
    if issue_count > 0:
        return RunStatus.PARTIAL
    return RunStatus.SUCCEEDED
```

`models.py` 需包含：`RunStatus(RUNNING/SUCCEEDED/FAILED/PARTIAL)`、`Issue`、`StepRecord`、`RunTrace`、`GenerationRun.start/finish`（`run_id` 用 UUID）。

- [ ] **步骤 4：运行确认通过**

- [ ] **步骤 5：提交** — `git commit -m "feat: 新增 GenerationRun 与状态判定"`

---

### Task 4: 需求摄入与输入拒绝（含完整代码步骤）

**文件：**
- 创建： `src/devspace_ai/domain/requirement/models.py`
- 创建： `src/devspace_ai/application/case_generation/errors.py`
- 创建： `src/devspace_ai/infrastructure/source/text_ingest.py`
- 创建： `tests/infrastructure/source/test_text_ingest.py`

**接口：**
- 消费： `Settings` limits
- 产出：
  - `RequirementDocument(source_type, title, text, metadata)`
  - `ingest_text(text, *, max_chars) -> RequirementDocument`
  - `ingest_upload(filename, raw_bytes, *, max_bytes, max_chars) -> RequirementDocument`
  - Raises `InputRejectedError(code, message)` for `INVALID_INPUT`, `INPUT_TOO_LONG`, `FILE_TOO_LARGE`, `UNSUPPORTED_FILE_TYPE`

- [ ] **步骤 1： 编写失败测试**

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

- [ ] **步骤 2： 运行，预期失败**

Run: `pytest tests/infrastructure/source/test_text_ingest.py -v`

- [ ] **步骤 3： Implement**

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

- [ ] **步骤 4： 运行，预期通过**

Run: `pytest tests/infrastructure/source/test_text_ingest.py -v`

- [ ] **步骤 5： 提交**

```bash
git add src/devspace_ai/domain/requirement src/devspace_ai/application/case_generation/errors.py src/devspace_ai/infrastructure/source tests/infrastructure/source
git commit -m "feat: add requirement ingest with explicit rejection errors"
```

---

### Task 5: ModelPort、确定性 Fake Model 与提示词（含完整代码步骤）

**文件：**
- 创建： `src/devspace_ai/application/port/outbound/model_port.py`
- 创建： `src/devspace_ai/infrastructure/prompt/case_generation.py`
- 创建： `src/devspace_ai/infrastructure/model/fake_model.py`
- 创建： `src/devspace_ai/infrastructure/model/factory.py`
- 创建： `tests/infrastructure/model/test_fake_model.py`

**接口：**
- 消费： `RequirementDocument`, settings
- 产出：
  - `ModelPort.generate_case_drafts(requirement_text, *, max_cases, language, domain_hint, repair_issues: list[str] | None) -> ModelGenerationResult`
  - `ModelGenerationResult(raw_drafts: list[dict], prompt_tokens, completion_tokens, model)`
  - `FakeModelAdapter` deterministic 2–3 drafts; at least one `test_data=null` and one non-null
  - `build_model_adapter(settings) -> ModelPort` chooses fake when `model_provider==fake` or api key missing

- [ ] **步骤 1： 编写失败测试**

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

- [ ] **步骤 2： 运行，预期失败**

Run: `pytest tests/infrastructure/model/test_fake_model.py -v`

- [ ] **步骤 3： 实现端口、Fake 与工厂**

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

- [ ] **步骤 4： 运行，预期通过**

Run: `pytest tests/infrastructure/model/test_fake_model.py -v`

- [ ] **步骤 5： 提交**

```bash
git add src/devspace_ai/application/port src/devspace_ai/infrastructure/model src/devspace_ai/infrastructure/prompt tests/infrastructure/model
git commit -m "feat: add ModelPort and deterministic Fake Model"
```

---

### Task 6: OpenAI 兼容适配器与 SQLite Run 仓储（含完整代码步骤）

**文件：**
- 创建： `src/devspace_ai/infrastructure/model/openai_compatible.py`
- 创建： `src/devspace_ai/application/port/outbound/run_repository_port.py`
- 创建： `src/devspace_ai/infrastructure/persistence/sqlite_run_repository.py`
- 创建： `tests/infrastructure/model/test_openai_compatible.py`
- 创建： `tests/infrastructure/persistence/test_sqlite_run_repository.py`

**接口：**
- 消费： `Settings`, `GenerationRun`
- 产出：
  - `OpenAICompatibleModelAdapter` calling `POST {base}/chat/completions` with JSON schema-ish prompt; parse `drafts` array from message content
  - `RunRepositoryPort.save(run)`, `get(run_id)`, `list_recent(limit=20)`
  - SQLite JSON serialization of drafts/issues/trace

- [ ] **步骤 1： 编写失败的仓储测试**

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

- [ ] **步骤 2： 实现 SQLite 仓储**

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

- [ ] **步骤 3： 使用 httpx MockTransport 编写 OpenAI 适配器测试**

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

- [ ] **步骤 4： 运行测试，预期通过**

Run: `pytest tests/infrastructure/persistence/test_sqlite_run_repository.py tests/infrastructure/model/test_openai_compatible.py -v`

- [ ] **步骤 5： 提交**

```bash
git add src/devspace_ai/infrastructure/persistence src/devspace_ai/infrastructure/model/openai_compatible.py src/devspace_ai/application/port/outbound/run_repository_port.py tests/infrastructure
git commit -m "feat: add OpenAI-compatible model adapter and SQLite run repository"
```

---

### Task 7: 应用层 Graph 服务（含完整代码步骤）

**文件：**
- 创建： `src/devspace_ai/application/dto/commands.py`
- 创建： `src/devspace_ai/application/dto/results.py`
- 创建： `src/devspace_ai/application/port/inbound/generate_case_drafts_port.py`
- 创建： `src/devspace_ai/application/case_generation/service.py`
- 创建： `tests/application/case_generation/test_service.py`

**接口：**
- 消费： `ModelPort`, `RunRepositoryPort`, `Settings`, ingest helpers, domain validators, `resolve_status`
- 产出： `CaseGenerationService.generate(command: GenerateCaseDraftsCommand) -> GenerateCaseDraftsResult`
- Command fields: `text: str | None`, `file_name: str | None`, `file_bytes: bytes | None`, `language`, `max_cases: int | None`, `domain_hint`
- Exactly one of text/file; enforce hard max cases; one validation repair retry; map raw dicts → `CaseDraft`; persist always before return (including timeout/failure)

- [ ] **步骤 1： 使用假端口编写失败的应用测试**

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

- [ ] **步骤 2： 实现 DTO 与服务**

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

- [ ] **步骤 3： 运行，预期通过**

Run: `pytest tests/application/case_generation/test_service.py -v`

- [ ] **步骤 4： 提交**

```bash
git add src/devspace_ai/application tests/application
git commit -m "feat: implement case generation graph service"
```

---

### Task 8: REST API（同步 multipart + 查询 Run）（含完整代码步骤）

**文件：**
- 创建： `src/devspace_ai/interfaces/rest/schemas.py`
- 创建： `src/devspace_ai/interfaces/rest/errors.py`
- 创建： `src/devspace_ai/interfaces/rest/routes_case_drafts.py`
- 修改： `src/devspace_ai/apps/api/main.py` (wire routes + DI)
- 创建： `tests/interfaces/rest/test_case_drafts_api.py`

**接口：**
- 消费： `CaseGenerationService`
- 产出：
  - `POST /api/v1/case-drafts/generate` multipart
  - `GET /api/v1/runs/{run_id}`
  - 400 body: `{"issues":[{"code","message",...}]}`
  - 200 body: run DTO with drafts/trace/issues/status

- [ ] **步骤 1： 使用 TestClient + Fake 模型编写 API 测试**

Tests:
1. paste text → 200 succeeded/partial with drafts
2. missing both fields → 400 `INVALID_INPUT`
3. too long text → 400 `INPUT_TOO_LONG` message contains limit
4. get run by id after generate

- [ ] **步骤 2： 实现路由并组装 `create_app`**

In `create_app`:
- build settings, model adapter, sqlite repo (use tmp path in tests via dependency override or constructor arg)
- mount router

- [ ] **步骤 3： 运行，预期通过**

Run: `pytest tests/interfaces/rest/test_case_drafts_api.py -v`

- [ ] **步骤 4： 提交**

```bash
git add src/devspace_ai/interfaces/rest src/devspace_ai/apps/api/main.py tests/interfaces/rest
git commit -m "feat: expose synchronous case draft generation API"
```

---

### Task 9: Jinja 调试页（含完整代码步骤）

**文件：**
- 创建： `src/devspace_ai/interfaces/web_debug/routes.py`
- 创建： `src/devspace_ai/interfaces/web_debug/templates/base.html`
- 创建： `src/devspace_ai/interfaces/web_debug/templates/index.html`
- 创建： `src/devspace_ai/interfaces/web_debug/templates/run_detail.html`
- 修改： `src/devspace_ai/apps/api/main.py` (mount debug routes + Jinja templates)
- 创建： `tests/interfaces/web_debug/test_debug_pages.py`

**接口：**
- 消费： same generate use case / REST internally (prefer calling application service from form POST, not duplicating logic)
- 产出：
  - `GET /debug/` form page
  - `POST /debug/generate` → render results + trace + issues + JSON copy block
  - `GET /debug/runs/{run_id}` replay

- [ ] **步骤 1： 编写失败的页面测试**

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

- [ ] **步骤 2： 实现 Jinja 模板与路由**

Keep UI minimal: textarea, file input, max_cases, domain_hint, submit; results list steps including `test_data`; show issues; link to run detail.

- [ ] **步骤 3： 运行，预期通过**

Run: `pytest tests/interfaces/web_debug/test_debug_pages.py -v`

- [ ] **步骤 4： 提交**

```bash
git add src/devspace_ai/interfaces/web_debug tests/interfaces/web_debug src/devspace_ai/apps/api/main.py
git commit -m "feat: add Jinja debug UI for case draft generation"
```

---


### Task 10: 文档硬化与全量质量门禁

**文件：**
- 完善：`README.md`、`docs/architecture.md`、`.env.example`
- 必要时微调 CI / Docker

**验收命令（必须全绿）：**

```bash
uv sync --all-extras --frozen
make lint          # ruff check + format --check
make typecheck     # mypy
make test          # pytest -v
```

**README 必须包含（中文）：**
1. 环境要求（Python 3.12、uv）
2. 安装与启动：`make sync` / `make run`
3. 调试页地址：`http://127.0.0.1:8000/debug/`
4. 模型配置方法与 Fake 默认行为
5. Docker 启动方式
6. 链接到设计规格与架构文档

- [ ] **步骤 1：** 补齐 README / architecture
- [ ] **步骤 2：** 跑全量门禁
- [ ] **步骤 3：**（可选）手工打开调试页粘贴需求验证
- [ ] **步骤 4：** 提交 — `docs: 完善 README 与 v1 交付说明`

---


## 4. 规格覆盖对照

| 规格要点 | 任务 |
| --- | --- |
| 生产工程/依赖锁定/CI/Docker | Task 1、10 |
| 轻量 DDD 分层 | 全任务 |
| CaseDraft + 可空 `test_data` | Task 2 |
| Run 状态 / issues | Task 3、7 |
| 粘贴上传 + 拒绝策略 | Task 4、8 |
| Fake + OpenAI 兼容 | Task 5、6 |
| 同步 Graph + 一次纠错 | Task 7 |
| REST multipart | Task 8 |
| Jinja 调试页 | Task 9 |
| 无密钥 CI 全绿 | Task 1、5、10 |
| 不写 TMS / 无鉴权 / 无 SPA | 通过范围省略保证 |

---

## 5. 实现前审阅门禁（必须）

**是的：本计划需要先审阅通过，再启动编码。**

建议审阅清单：

1. **技术基线**：Python 3.12 + uv + 上表锁定版本是否接受  
2. **范围**：v1 仍是「调试页闭环」，不含 `cdp-suite` 入库  
3. **任务切分**：10 个任务是否可按序交付、每任务可独立测试  
4. **生产要素**：锁文件、CI、Docker、日志、健康检查是否够用（鉴权/多租户明确不做）

审阅方式任选：

- 人工阅读本文并回复「计划通过」或修改点  
- 对本文再跑一轮 `/grill-me`（推荐，阈值按 plan/spec 严格）

**未通过审阅前，不启动 Subagent-Driven / Inline Execution。**

---

## 6. 自检记录

- 占位符扫描：无 TBD/TODO/「稍后实现」类步骤说明  
- 类型一致性：`CaseDraft` / `GenerationRun` / `Issue` / `GenerateCaseDraftsCommand` 在各任务命名一致  
- 依赖版本：主依赖已钉死；传递依赖以 `uv.lock` 为准  
- mypy 版本：锁定 `mypy==2.3.0`；若 `uv lock` 与传递依赖冲突，以可解析版本回写本节版本表
