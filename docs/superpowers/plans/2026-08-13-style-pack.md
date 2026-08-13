# 用例风格包（Style Pack）实现计划

> **面向执行代理：** 必选子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐步实现。步骤使用 checkbox（`- [ ]`）跟踪。

**目标：** 在 `devspace-ai` 落地可维护的用例风格包：调试页结构化维护、生成时点选（含 2 个只读内置示例）、范文注入提示词，并对该次 Run 快照范文。

**架构：** 沿用轻量 DDD。`StylePack` 领域不变量 + `StylePackRepositoryPort`（仅自建包）+ 应用层「内置目录 ∪ 仓储」。生成 Graph 在 `ingest` 与 `generate` 之间增加 `load_style_context`。写 API 仅在 `debug_ui_enabled()` 时挂载。

**规格依据：** `docs/superpowers/specs/2026-08-13-style-pack-design.md`

**Tech Stack：** Python 3.12、FastAPI、SQLAlchemy 2 同步 + Alembic + PostgreSQL 16、Jinja2、pytest。不引入向量库。

**文档语言：** 计划正文中文；代码标识符、API 路径、错误码英文。

## Global Constraints

- 不上 RAG / embedding / 向量检索
- 不鉴权、无多租户；`GET` 风格包始终挂载；`POST/PUT/DELETE` 仅调试 UI 开启时挂载
- 内置 2 包不入库、只读；`key` 前缀 `example.` 保留
- 每包最多 5 条需求、每条最多 3 条用例、合计最多 15 条；自建包最多 50 个
- 不允许空包；生成未选包 = v1 行为
- Fake 模型忽略范文；CI 无密钥必须全绿
- 用户可见报错中文；`issues[]` 含 `code`/`message`/`field?`
- 本轮不改 `.github/workflows`
- 开发在功能分支，禁止直接提交 `main`

---

## 文件地图

| 路径 | 职责 |
| --- | --- |
| `src/devspace_ai/domain/style_pack/errors.py` | `StylePackError(code, message, field?)` |
| `src/devspace_ai/domain/style_pack/models.py` | `StyleExample`、`StylePack.validate()` |
| `src/devspace_ai/infrastructure/style_pack/builtins.py` | 2 个内置包常量与 `get_builtin`/`list_builtins` |
| `src/devspace_ai/application/port/outbound/style_pack_repository_port.py` | 自建包仓储端口 |
| `src/devspace_ai/application/style_pack/service.py` | 读合并内置；写校验 + 仓储 |
| `src/devspace_ai/application/style_pack/errors.py` | `IssuesRejectedError`、`PackNotFoundError` |
| `alembic/versions/20260813_0002_style_packs.py` | `style_packs` 表 |
| `src/devspace_ai/infrastructure/persistence/models.py` | `StylePackRow` |
| `src/devspace_ai/infrastructure/persistence/pg_style_pack_repository.py` | PG 适配 |
| `src/devspace_ai/interfaces/rest/routes_style_packs.py` | 读路由 + 写路由拆分 |
| `src/devspace_ai/interfaces/rest/schemas.py` | Pack DTO；`GenerationRunDTO.style_pack` |
| `src/devspace_ai/infrastructure/prompt/case_generation.py` | 注入范文块 |
| `src/devspace_ai/application/case_generation/service.py` | `load_style_context` + 快照 |
| `src/devspace_ai/interfaces/web_debug/` | 列表/查看/新建编辑表单 + 生成下拉 |
| `README.md`、`docs/architecture.md` | 一小节说明 |

---

### Task 1: StylePack 领域不变量

**Files:**
- Create: `src/devspace_ai/domain/style_pack/errors.py`
- Create: `src/devspace_ai/domain/style_pack/models.py`
- Create: `src/devspace_ai/domain/style_pack/__init__.py`
- Test: `tests/domain/style_pack/test_models.py`

**Interfaces:**
- Consumes: `CaseDraft.validate()`、`CaseDraftValidationError.field`
- Produces: `StyleExample`、`StylePack.validate() -> None`；失败抛 `StylePackError`

- [ ] **Step 1: 写失败测试**

```python
# tests/domain/style_pack/test_models.py
import pytest

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import StyleExample, StylePack


def _draft() -> CaseDraft:
    return CaseDraft(
        title="原路退款成功",
        preconditions=["订单已支付"],
        steps=[TestStep(action="点击退款", expected="退款成功", test_data="100.00")],
        priority="P1",
        tags=["pay"],
    )


def _pack(**kwargs: object) -> StylePack:
    defaults: dict[str, object] = {
        "id": "11111111-1111-4111-8111-111111111111",
        "key": "cdp.payment.api",
        "name": "支付接口",
        "description": None,
        "examples": [StyleExample(label="退款", requirement_text="用户申请退款", drafts=[_draft()])],
        "builtin": False,
    }
    defaults.update(kwargs)
    return StylePack(**defaults)  # type: ignore[arg-type]


def test_valid_pack_normalizes() -> None:
    pack = _pack(name="  支付接口  ")
    pack.validate()
    assert pack.name == "支付接口"


def test_empty_examples_rejected() -> None:
    pack = _pack(examples=[])
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "EMPTY_PACK"


def test_reserved_key_rejected_for_user_pack() -> None:
    pack = _pack(key="example.payment.api")
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "INVALID_KEY"


def test_reserved_key_allowed_for_builtin() -> None:
    pack = _pack(key="example.payment.api", builtin=True, name="示例 · 支付接口")
    pack.validate()


def test_too_many_examples() -> None:
    examples = [
        StyleExample(label=None, requirement_text=f"需求{i}", drafts=[_draft()]) for i in range(6)
    ]
    pack = _pack(examples=examples)
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "PACK_LIMIT"


def test_too_many_drafts_in_one_example() -> None:
    pack = _pack(
        examples=[StyleExample(label=None, requirement_text="需求", drafts=[_draft()] * 4)]
    )
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "PACK_LIMIT"


def test_empty_requirement_invalid_example() -> None:
    pack = _pack(examples=[StyleExample(label=None, requirement_text="  ", drafts=[_draft()])])
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "INVALID_EXAMPLE"
    assert ei.value.field == "examples[0].requirement_text"


def test_invalid_name() -> None:
    pack = _pack(name="   ")
    with pytest.raises(StylePackError) as ei:
        pack.validate()
    assert ei.value.code == "INVALID_NAME"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/domain/style_pack/test_models.py -v
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 最小实现**

```python
# src/devspace_ai/domain/style_pack/errors.py
"""风格包不变量失败。"""


class StylePackError(ValueError):
    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
```

```python
# src/devspace_ai/domain/style_pack/models.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from devspace_ai.domain.case_draft.errors import CaseDraftValidationError
from devspace_ai.domain.case_draft.models import CaseDraft
from devspace_ai.domain.style_pack.errors import StylePackError

KEY_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?$")
RESERVED_KEY_PREFIX = "example."
MAX_EXAMPLES = 5
MAX_DRAFTS_PER_EXAMPLE = 3
MAX_DRAFTS_PER_PACK = 15
MAX_NAME_LEN = 80
MAX_DESCRIPTION_LEN = 500
MAX_LABEL_LEN = 80
MAX_USER_PACKS = 50


@dataclass
class StyleExample:
    requirement_text: str
    drafts: list[CaseDraft]
    label: str | None = None


@dataclass
class StylePack:
    id: str
    key: str
    name: str
    examples: list[StyleExample]
    description: str | None = None
    builtin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def draft_count(self) -> int:
        return sum(len(ex.drafts) for ex in self.examples)

    def validate(self) -> None:
        name = (self.name or "").strip()
        if not name or len(name) > MAX_NAME_LEN:
            raise StylePackError("INVALID_NAME", "名称不能为空且最多 80 字", field="name")
        self.name = name
        key = (self.key or "").strip()
        if not KEY_PATTERN.fullmatch(key):
            raise StylePackError(
                "INVALID_KEY",
                "代号仅允许小写字母、数字、点、连字符，长度 1～64",
                field="key",
            )
        if not self.builtin and key.startswith(RESERVED_KEY_PREFIX):
            raise StylePackError(
                "INVALID_KEY",
                "example. 前缀为系统示例保留",
                field="key",
            )
        self.key = key
        if self.description is not None:
            desc = self.description.strip()
            if len(desc) > MAX_DESCRIPTION_LEN:
                raise StylePackError("INVALID_INPUT", "说明最多 500 字", field="description")
            self.description = desc or None
        if not self.examples:
            raise StylePackError("EMPTY_PACK", "风格包至少需要一组范文", field="examples")
        if len(self.examples) > MAX_EXAMPLES:
            raise StylePackError(
                "PACK_LIMIT",
                f"需求条数 {len(self.examples)} 超出上限 {MAX_EXAMPLES}",
                field="examples",
            )
        total = 0
        for i, ex in enumerate(self.examples):
            req = (ex.requirement_text or "").strip()
            if not req:
                raise StylePackError(
                    "INVALID_EXAMPLE",
                    "需求片段不能为空",
                    field=f"examples[{i}].requirement_text",
                )
            ex.requirement_text = req
            if ex.label is not None:
                label = ex.label.strip()
                if len(label) > MAX_LABEL_LEN:
                    raise StylePackError(
                        "INVALID_INPUT",
                        "备注最多 80 字",
                        field=f"examples[{i}].label",
                    )
                ex.label = label or None
            n = len(ex.drafts)
            if n < 1 or n > MAX_DRAFTS_PER_EXAMPLE:
                raise StylePackError(
                    "INVALID_EXAMPLE",
                    f"每条需求下用例须为 1～{MAX_DRAFTS_PER_EXAMPLE} 条",
                    field=f"examples[{i}].drafts",
                )
            for j, draft in enumerate(ex.drafts):
                try:
                    draft.validate()
                except CaseDraftValidationError as exc:
                    raise StylePackError(
                        "INVALID_EXAMPLE",
                        str(exc),
                        field=f"examples[{i}].drafts[{j}].{exc.field or 'draft'}",
                    ) from exc
            total += n
        if total > MAX_DRAFTS_PER_PACK:
            raise StylePackError(
                "PACK_LIMIT",
                f"用例合计 {total} 超出上限 {MAX_DRAFTS_PER_PACK}",
                field="examples",
            )
```

```python
# src/devspace_ai/domain/style_pack/__init__.py
```

KEY_PATTERN 允许 `a`、`cdp.payment.api`、`example.payment.api`；总长 ≤64（正则已限制）。单字符由 `{0,62}` 前的首字符匹配。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/domain/style_pack/test_models.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/domain/style_pack tests/domain/style_pack
git commit -m "$(cat <<'EOF'
feat: 新增 StylePack 领域不变量。

EOF
)"
```

---

### Task 2: 两个内置示例 fixture

**Files:**
- Create: `src/devspace_ai/infrastructure/style_pack/builtins.py`
- Create: `src/devspace_ai/infrastructure/style_pack/__init__.py`
- Test: `tests/infrastructure/style_pack/test_builtins.py`

**Interfaces:**
- Consumes: `StylePack.validate()`
- Produces: `BUILTIN_PAYMENT_ID`、`BUILTIN_MARKETING_ID`、`list_builtins() -> list[StylePack]`、`get_builtin(id: str) -> StylePack | None`

- [ ] **Step 1: 写失败测试**

```python
# tests/infrastructure/style_pack/test_builtins.py
from devspace_ai.infrastructure.style_pack.builtins import (
    BUILTIN_MARKETING_ID,
    BUILTIN_PAYMENT_ID,
    get_builtin,
    list_builtins,
)


def test_two_builtins_validate_and_cover_structure() -> None:
    packs = list_builtins()
    assert len(packs) == 2
    assert {p.id for p in packs} == {BUILTIN_PAYMENT_ID, BUILTIN_MARKETING_ID}
    for pack in packs:
        pack.validate()
        assert pack.builtin is True
        assert pack.key.startswith("example.")
        assert len(pack.examples) >= 2
        assert any(len(ex.drafts) >= 2 for ex in pack.examples)
        datas = [
            step.test_data
            for ex in pack.examples
            for d in ex.drafts
            for step in d.steps
        ]
        assert any(x is None for x in datas)
        assert any(x is not None for x in datas)


def test_get_builtin_unknown() -> None:
    assert get_builtin("not-a-builtin") is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/infrastructure/style_pack/test_builtins.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 fixture**

```python
# src/devspace_ai/infrastructure/style_pack/builtins.py
from datetime import UTC, datetime

from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.models import StyleExample, StylePack

BUILTIN_PAYMENT_ID = "00000000-0000-4000-8000-000000000001"
BUILTIN_MARKETING_ID = "00000000-0000-4000-8000-000000000002"
_TS = datetime(2026, 8, 13, tzinfo=UTC)


def _step(action: str, expected: str, test_data: str | None = None) -> TestStep:
    return TestStep(action=action, expected=expected, test_data=test_data)


def _payment() -> StylePack:
    return StylePack(
        id=BUILTIN_PAYMENT_ID,
        key="example.payment.api",
        name="示例 · 支付接口",
        description="支付/退款接口测试写法教材",
        builtin=True,
        created_at=_TS,
        updated_at=_TS,
        examples=[
            StyleExample(
                label="退款成功",
                requirement_text="用户已支付成功，在订单详情点击退款，退款金额等于实付金额，应退回原支付渠道。",
                drafts=[
                    CaseDraft(
                        title="订单详情原路退款成功",
                        preconditions=["订单已支付", "退款渠道可用"],
                        steps=[
                            _step("打开订单详情", "页面展示实付金额", None),
                            _step("点击退款并确认金额", "提示退款受理", "100.00"),
                        ],
                        priority="P0",
                        tags=["pay", "refund"],
                    )
                ],
            ),
            StyleExample(
                label="超额退款",
                requirement_text="用户尝试将退款金额填写为大于实付金额。",
                drafts=[
                    CaseDraft(
                        title="退款金额超过实付被拒绝",
                        preconditions=["订单已支付"],
                        steps=[_step("提交超额退款", "提示金额非法", "99999")],
                        priority="P1",
                        tags=["pay", "negative"],
                    ),
                    CaseDraft(
                        title="重复提交退款",
                        preconditions=["退款已受理"],
                        steps=[_step("再次点击退款", "提示请勿重复提交", None)],
                        priority="P2",
                        tags=["pay"],
                    ),
                ],
            ),
        ],
    )


def _marketing() -> StylePack:
    return StylePack(
        id=BUILTIN_MARKETING_ID,
        key="example.marketing.web",
        name="示例 · 营销活动页",
        description="活动页领取与核销的界面测试写法教材",
        builtin=True,
        created_at=_TS,
        updated_at=_TS,
        examples=[
            StyleExample(
                label="领券",
                requirement_text="登录用户在活动页点击领取优惠券，库存充足时应领取成功。",
                drafts=[
                    CaseDraft(
                        title="活动页领取优惠券成功",
                        preconditions=["已登录", "券有库存"],
                        steps=[
                            _step("打开活动页", "展示领取按钮", None),
                            _step("点击领取", "提示领取成功并展示券码", "COUPON1"),
                        ],
                        priority="P1",
                        tags=["promo"],
                    )
                ],
            ),
            StyleExample(
                label="核销",
                requirement_text="用户在结算页使用已领取的优惠券抵扣。",
                drafts=[
                    CaseDraft(
                        title="结算页核销优惠券",
                        preconditions=["购物车有商品", "券未过期"],
                        steps=[_step("选择优惠券并提交订单", "应付金额已抵扣", None)],
                        priority="P1",
                        tags=["promo", "checkout"],
                    ),
                    CaseDraft(
                        title="过期券不可用",
                        preconditions=["券已过期"],
                        steps=[_step("尝试勾选过期券", "券置灰并提示过期", None)],
                        priority="P2",
                        tags=["promo", "negative"],
                    ),
                ],
            ),
        ],
    )


def list_builtins() -> list[StylePack]:
    packs = [_payment(), _marketing()]
    for pack in packs:
        pack.validate()
    return packs


def get_builtin(pack_id: str) -> StylePack | None:
    for pack in list_builtins():
        if pack.id == pack_id:
            return pack
    return None
```

`src/devspace_ai/infrastructure/style_pack/__init__.py` 可为空。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/infrastructure/style_pack/test_builtins.py tests/domain/style_pack/test_models.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/devspace_ai/infrastructure/style_pack tests/infrastructure/style_pack
git commit -m "$(cat <<'EOF'
feat: 增加只读内置风格包示例。

EOF
)"
```

---

### Task 3: PostgreSQL 仓储与迁移

**Files:**
- Create: `alembic/versions/20260813_0002_style_packs.py`
- Modify: `src/devspace_ai/infrastructure/persistence/models.py`
- Create: `src/devspace_ai/application/port/outbound/style_pack_repository_port.py`
- Create: `src/devspace_ai/infrastructure/persistence/pg_style_pack_repository.py`
- Test: `tests/infrastructure/persistence/test_pg_style_pack_repository.py`
- Modify: 所有 `DROP TABLE IF EXISTS generation_runs` 的测试夹具，同时 `DROP TABLE IF EXISTS style_packs CASCADE`

**Interfaces:**
- Consumes: `StylePack`、`StyleExample`、`CaseDraft`
- Produces: `StylePackRepositoryPort`：`list_user() -> list[StylePack]`（`updated_at` 倒序）、`get(id) -> StylePack | None`、`create(pack) -> StylePack`、`update(pack) -> StylePack`、`delete(id) -> bool`、`count() -> int`、`get_by_key(key) -> StylePack | None`

- [ ] **Step 1: 写失败测试**

仓储 `create` 在 `get_by_key` 已存在时抛 `StylePackError("DUPLICATE_KEY", "代号已存在", field="key")`。

```python
# tests/infrastructure/persistence/test_pg_style_pack_repository.py
import os
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from devspace_ai.domain.case_draft.models import CaseDraft, TestStep
from devspace_ai.domain.style_pack.errors import StylePackError
from devspace_ai.domain.style_pack.models import StyleExample, StylePack
from devspace_ai.infrastructure.persistence.pg_style_pack_repository import (
    PgStylePackRepository,
)


@pytest.fixture()
def db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai_test",
    )


@pytest.fixture()
def repo(db_url: str) -> PgStylePackRepository:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS style_packs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS generation_runs CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    return PgStylePackRepository(db_url)


def _pack(key: str = "cdp.payment.api") -> StylePack:
    return StylePack(
        id=str(uuid4()),
        key=key,
        name="支付接口",
        examples=[
            StyleExample(
                label="退款",
                requirement_text="用户申请退款",
                drafts=[
                    CaseDraft(
                        title="原路退款",
                        steps=[TestStep(action="点退款", expected="成功", test_data="1")],
                    )
                ],
            )
        ],
    )


def test_create_get_delete_count(repo: PgStylePackRepository) -> None:
    created = repo.create(_pack())
    loaded = repo.get(created.id)
    assert loaded is not None
    assert loaded.key == "cdp.payment.api"
    assert loaded.examples[0].requirement_text == "用户申请退款"
    assert repo.count() == 1
    with pytest.raises(StylePackError) as ei:
        repo.create(_pack())
    assert ei.value.code == "DUPLICATE_KEY"
    assert repo.delete(created.id) is True
    assert repo.get(created.id) is None
    assert repo.count() == 0
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/infrastructure/persistence/test_pg_style_pack_repository.py -v
```

Expected: FAIL

- [ ] **Step 3: 迁移 + ORM + 仓储**

迁移 `revision = "20260813_0002"`，`down_revision = "20260812_0001"`。表 `style_packs`：

- `id` String(36) PK
- `key` String(64) unique not null
- `name` String(80) not null
- `description` Text nullable
- `examples` JSONB not null
- `created_at` / `updated_at` DateTime(timezone=True) not null；`updated_at` 建索引

JSONB `examples` 形状：`[{"label", "requirement_text", "drafts": [CaseDraft asdict]}]`。`drafts` 内 `steps` 为 `TestStep` 字典。读写与 `pg_run_repository` 同样用 `asdict` / 手工还原 `CaseDraft`。

`create`：若 `get_by_key` 命中 → `StylePackError DUPLICATE_KEY`；否则插入，`created_at`/`updated_at` = now UTC。  
`update`：按 id merge，刷新 `updated_at`，不改 `key`。找不到返回由应用层处理（仓储 `update` 找不到 raise 或返回 None——**约定返回 `None`，应用层变 404**）。  
`delete`：找不到返回 `False`。

把 `tests/infrastructure/persistence/test_pg_run_repository.py`、`tests/interfaces/rest/test_case_drafts_api.py`、`tests/interfaces/web_debug/test_debug_pages.py` 的 DROP 补上 `style_packs`。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/infrastructure/persistence/test_pg_style_pack_repository.py tests/infrastructure/persistence/test_pg_run_repository.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: 新增 style_packs 表与 PostgreSQL 仓储。

EOF
)"
```

---

### Task 4: StylePack 应用服务（读合并内置、写校验）

**Files:**
- Create: `src/devspace_ai/application/style_pack/errors.py`
- Create: `src/devspace_ai/application/style_pack/service.py`
- Create: `src/devspace_ai/application/style_pack/__init__.py`
- Modify: `src/devspace_ai/application/case_generation/errors.py`（`InputRejectedError` 增加可选 `field`）
- Modify: `src/devspace_ai/interfaces/rest/errors.py`（映射 `field`；新增两类异常）
- Test: `tests/application/style_pack/test_service.py`

**Interfaces:**
- Consumes: `list_builtins`、`get_builtin`、`StylePackRepositoryPort`、`MAX_USER_PACKS`
- Produces: `StylePackService.list_all / get / create / update / delete`

`PackNotFoundError` → HTTP 404 `{issues:[{code:PACK_NOT_FOUND,message}]}`  
`IssuesRejectedError(issues: list[Issue])` → HTTP 400  
`InputRejectedError` 单条 400，JSON 含 `field`（若有）

内存假仓储用于单测（dict）。

- [ ] **Step 1: 写失败测试**

覆盖：

1. `list_all` 空仓储仍 2 条 builtin 在前  
2. `create` 空 examples → `EMPTY_PACK`  
3. `create` 第 51 个用户包 → `PACK_LIMIT`（可 mock `count()==50`）  
4. `create` key=`example.x` → `INVALID_KEY`  
5. `update`/`delete` 内置 id → `InputRejectedError` code `PACK_READONLY`  
6. `get` 内置 id 成功；未知 id → `PackNotFoundError`  
7. `create` 成功后 `list_all` 长度为 3（2 builtin + 1）

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/application/style_pack/test_service.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现服务**

```python
class StylePackService:
    def __init__(self, repo: StylePackRepositoryPort) -> None:
        self.repo = repo

    def list_all(self) -> list[StylePack]:
        return [*list_builtins(), *self.repo.list_user()]

    def get(self, pack_id: str) -> StylePack:
        builtin = get_builtin(pack_id)
        if builtin is not None:
            return builtin
        pack = self.repo.get(pack_id)
        if pack is None:
            raise PackNotFoundError()
        return pack

    def create(self, pack: StylePack) -> StylePack:
        pack.builtin = False
        try:
            pack.validate()
        except StylePackError as exc:
            raise InputRejectedError(exc.code, exc.message, field=exc.field) from exc
        if self.repo.count() >= MAX_USER_PACKS:
            raise InputRejectedError(
                "PACK_LIMIT",
                f"自建风格包最多 {MAX_USER_PACKS} 个",
            )
        return self.repo.create(pack)

    def update(self, pack: StylePack) -> StylePack:
        if get_builtin(pack.id) is not None:
            raise InputRejectedError("PACK_READONLY", "系统示例不能修改")
        existing = self.repo.get(pack.id)
        if existing is None:
            raise PackNotFoundError()
        pack.key = existing.key
        pack.builtin = False
        try:
            pack.validate()
        except StylePackError as exc:
            raise InputRejectedError(exc.code, exc.message, field=exc.field) from exc
        updated = self.repo.update(pack)
        if updated is None:
            raise PackNotFoundError()
        return updated

    def delete(self, pack_id: str) -> None:
        if get_builtin(pack_id) is not None:
            raise InputRejectedError("PACK_READONLY", "系统示例不能删除")
        if not self.repo.delete(pack_id):
            raise PackNotFoundError()
```

`PackNotFoundError.message = "风格包不存在"`，`code = PACK_NOT_FOUND`。

异常处理器：`PackNotFoundError` → 404；`StylePackError` 也可直接 400（create 路径若让 `StylePackError` 冒泡，在 REST 层 catch 或应用层转 `InputRejectedError`）。**约定应用层把 `StylePackError` 转成 `InputRejectedError(code, message, field)`**，REST 只处理 `InputRejectedError` / `PackNotFoundError` / `IssuesRejectedError`。

扩展 `InputRejectedError.__init__(self, code, message, field: str | None = None)`。  
扩展 handler：`content={"issues":[{"code","message","field": exc.field}]}`（field 为 None 时仍可输出 `null`，与 v1 Issue DTO 一致）。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/application/style_pack/test_service.py tests/interfaces/rest/test_case_drafts_api.py -v
```

Expected: PASS。handler 的 issues 项始终包含 `field` 键（无则为 `null`）。既有测试只断言 `code`，不受影响。

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: 实现风格包应用服务（内置合并与只读保护）。

EOF
)"
```

---

### Task 5: REST 读始终挂载、写随调试 UI

**Files:**
- Modify: `src/devspace_ai/interfaces/rest/schemas.py`
- Create: `src/devspace_ai/interfaces/rest/routes_style_packs.py`
- Modify: `src/devspace_ai/apps/api/main.py`
- Test: `tests/interfaces/rest/test_style_packs_api.py`

**Interfaces:**
- Consumes: `StylePackService`，挂在 `app.state.style_pack_service`
- Produces: JSON API 如下

| 方法 | 路径 | 挂载 |
| --- | --- | --- |
| GET | `/api/v1/style-packs` | 始终 |
| GET | `/api/v1/style-packs/{id}` | 始终 |
| POST | `/api/v1/style-packs` | 仅 debug UI |
| PUT | `/api/v1/style-packs/{id}` | 仅 debug UI |
| DELETE | `/api/v1/style-packs/{id}` | 仅 debug UI |

列表项 DTO：`id, key, name, description, requirement_count, draft_count, updated_at, builtin`  
详情另含 `examples`（与领域 JSON 同形）。POST 201；DELETE 204。

`create_app`：构造 `PgStylePackRepository` + `StylePackService`；`include_router(read_router)`；若 `debug_ui_enabled()` 再 `include_router(write_router)` 且继续挂 debug 页。

- [ ] **Step 1: 写失败测试**

夹具 A：`app_env=local`（写开启）。夹具 B：`app_env=prod, enable_debug_ui=False`（写关闭）。DROP 含 `style_packs`。

1. B：`GET /api/v1/style-packs` → 200，至少 2 条 `builtin true`  
2. B：`POST /api/v1/style-packs` → 404  
3. A：POST 合法包 → 201，`builtin false`  
4. A：PUT/DELETE 内置 id → 400 `PACK_READONLY`  
5. A：GET 未知 id → 404 `PACK_NOT_FOUND`  
6. A：POST `key=example.foo` → 400 `INVALID_KEY`

POST body 示例：

```json
{
  "key": "cdp.payment.api",
  "name": "支付接口",
  "description": null,
  "examples": [
    {
      "label": "退款成功",
      "requirement_text": "用户申请全额退款",
      "drafts": [
        {
          "title": "原路退款成功",
          "preconditions": ["已支付"],
          "steps": [{"action": "点退款", "expected": "成功", "test_data": "100"}],
          "priority": "P1",
          "tags": ["pay"],
          "rationale": null
        }
      ]
    }
  ]
}
```

Pydantic 模型 `extra=forbid`。PUT 无 `key` 字段。

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/interfaces/rest/test_style_packs_api.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现路由与 DTO，接线 `create_app`**

把 `StylePack` ↔ DTO 的转换放在 `schemas.py`（`pack_to_list_dto` / `pack_to_detail_dto` / `body_to_style_pack`）。POST 服务端 `uuid4()` 生成 id。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/interfaces/rest/test_style_packs_api.py tests/apps/test_health.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: 暴露风格包 REST（读始终可用，写随调试 UI）。

EOF
)"
```

---

### Task 6: 提示词注入范文

**Files:**
- Modify: `src/devspace_ai/infrastructure/prompt/case_generation.py`
- Modify: `src/devspace_ai/application/port/outbound/model_port.py`（`style_pack: StylePack | None`）
- Modify: `src/devspace_ai/infrastructure/model/fake_model.py`、`openai_compatible.py`
- Modify: 所有实现 `generate_case_drafts` 的测试假对象（`tests/application/case_generation/test_service.py` 的 `ScriptedModel`、`tests/infrastructure/model/test_*.py`）
- Test: `tests/infrastructure/prompt/test_case_generation.py`

**Interfaces:**
- Consumes: `StylePack`
- Produces: `build_messages(..., style_pack: StylePack | None = None)`

- [ ] **Step 1: 写失败测试**

```python
from devspace_ai.infrastructure.prompt.case_generation import build_messages
from devspace_ai.infrastructure.style_pack.builtins import get_builtin, BUILTIN_PAYMENT_ID


def test_messages_include_style_pack_block() -> None:
    pack = get_builtin(BUILTIN_PAYMENT_ID)
    assert pack is not None
    msgs = build_messages(
        "分期订单部分退款",
        max_cases=10,
        language="zh-CN",
        domain_hint="金融",
        repair_issues=None,
        style_pack=pack,
    )
    user = str(msgs[1]["content"])
    assert "Style pack:" in user
    assert pack.key in user
    assert pack.examples[0].requirement_text in user
    assert "Domain hint:" in user
    system = str(msgs[0]["content"])
    assert "范文" in system or "style" in system.lower() or "imitate" in system.lower()


def test_messages_without_pack_have_no_style_block() -> None:
    msgs = build_messages(
        "登录",
        max_cases=3,
        language="zh-CN",
        domain_hint=None,
        repair_issues=None,
        style_pack=None,
    )
    assert "Style pack:" not in str(msgs[1]["content"])
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/infrastructure/prompt/test_case_generation.py -v
```

Expected: FAIL

- [ ] **Step 3: 改 `build_messages` 与调用链**

user 顺序：需求正文 → 若有包则 `Style pack: {name} ({key})` + 每组 `Example N` + requirement + `json.dumps` drafts → 若有 hint 则 `Domain hint:`。

system 追加：`When a style pack is provided, imitate its structure, step granularity, and wording; do not copy the example requirements as the new cases.`

`ModelPort.generate_case_drafts` 增加只读参数 `style_pack: StylePack | None`。Fake **忽略**该参数。OpenAI 适配器把它传入 `build_messages`。同步改所有测试假模型签名，否则 mypy/运行失败。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/infrastructure/prompt/test_case_generation.py tests/infrastructure/model tests/application/case_generation/test_service.py -v
uv run mypy
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: 生成提示词支持注入风格包范文。

EOF
)"
```

---

### Task 7: 生成 Graph 加载风格包并快照

**Files:**
- Modify: `src/devspace_ai/application/dto/commands.py`（`style_pack_id: str | None = None`）
- Modify: `src/devspace_ai/application/dto/results.py`（`style_pack: StylePack | None = None`）
- Modify: `src/devspace_ai/application/case_generation/service.py`
- Modify: `src/devspace_ai/infrastructure/persistence/pg_run_repository.py`（payload 键 `style_pack`）
- Modify: `src/devspace_ai/interfaces/rest/schemas.py`（`GenerationRunDTO.style_pack`）
- Modify: `src/devspace_ai/interfaces/rest/routes_case_drafts.py`、`web_debug/routes.py`（form 字段）
- Modify: `src/devspace_ai/apps/api/main.py`（`CaseGenerationService` 注入 `StylePackService`）
- Test: `tests/application/case_generation/test_service.py` 追加；`tests/interfaces/rest/test_case_drafts_api.py` 追加

**Interfaces:**
- Consumes: `StylePackService.get`
- Produces: 选包时 trace 步 `load_style_context`；payload/`DTO.style_pack` 快照（含 `builtin`）；未选则为 `null`；不写该步

UUID：使用 `uuid.UUID(style_pack_id)`，失败 → `InputRejectedError("INVALID_INPUT", "风格包 id 格式无效")`。  
`PackNotFoundError` 在 generate 路径转成 `InputRejectedError("PACK_NOT_FOUND", "风格包不存在")`（400，不建 Run）。  
超长：`len(requirement) + len(范文块文本)` > `max_text_chars` → `INPUT_TOO_LONG`，message 含当前长度、上限、「已计入风格包范文」。范文块文本 = 实际拼进 user 的 Style pack 段（可抽 `format_style_pack_block(pack) -> str` 供 prompt 与计数共用）。

`CaseGenerationService.__init__(self, settings, model, runs, style_packs: StylePackService)`。

快照 JSON：`{"id","key","name","description","builtin","examples":[...]}`。反序列化旧 Run 无该键 → `style_pack=None`。

`summary`：`f"{pack.name}（{pack.key}），需求 {len(pack.examples)} 组，用例 {pack.draft_count()} 条"`

- [ ] **Step 1: 写失败测试**

`CaseGenerationService` 测试注入内存 `StylePackService`。

1. 带内置 id：`ScriptedModel` 收到的 `style_pack` 非 None；trace 含 `load_style_context`；result.style_pack.builtin is True  
2. 不带 id：模型 `style_pack is None`；trace 无该步；result.style_pack is None  
3. 未知 UUID：`pytest.raises(InputRejectedError)` code `PACK_NOT_FOUND`，`model.calls == 0`，repo 无新 run  
4. 非法 id `"abc"`：`INVALID_INPUT`，不调模型  

REST：`data={"text":"登录","style_pack_id": BUILTIN_PAYMENT_ID}` → 200，`style_pack.builtin true`，trace 含 `load_style_context`。

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/application/case_generation/test_service.py tests/interfaces/rest/test_case_drafts_api.py -v
```

Expected: 新断言 FAIL

- [ ] **Step 3: 实现加载、快照、form 字段、DTO**

`result_to_dto` / `run_to_dto` 映射 `style_pack`（可用与详情相同的 DTO，未选 `null`）。

Persist 测试：`tests/infrastructure/persistence/test_pg_run_repository.py` 增加「带 style_pack 快照保存再读回」；无该键的旧 payload 仍能 get。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/application/case_generation tests/interfaces/rest tests/infrastructure/persistence -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: 生成流程加载风格包并快照到 Run。

EOF
)"
```

---

### Task 8: 调试页维护与生成下拉

**Files:**
- Modify: `src/devspace_ai/interfaces/web_debug/templates/base.html`（导航「风格包」）
- Modify: `src/devspace_ai/interfaces/web_debug/templates/index.html`（下拉）
- Create: `templates/style_packs_list.html`、`style_pack_view.html`、`style_pack_form.html`
- Create: `src/devspace_ai/interfaces/web_debug/static/style_pack_form.js`（或内联于 form 模板，少量 JS）
- Modify: `src/devspace_ai/interfaces/web_debug/routes.py`
- Test: `tests/interfaces/web_debug/test_debug_pages.py` 追加；新建 `tests/interfaces/web_debug/test_style_pack_pages.py`

**Interfaces:**
- Consumes: 同一 `StylePackService` 与 generate API 语义
- Produces: 规格 6.1 路由

| 方法 | 路径 |
| --- | --- |
| GET | `/debug/style-packs` |
| GET | `/debug/style-packs/new?from=` |
| GET | `/debug/style-packs/{id}` |
| GET | `/debug/style-packs/{id}/edit` |

表单用 JS 增删需求/用例/步骤，submit 时 `fetch` `POST/PUT /api/v1/style-packs`，JSON body 与 REST 相同。删除 `fetch DELETE` + `confirm`。

内置：列表分区「系统示例」只有「查看」「用此示例创建」；`/edit` 对内置 id **302 到** `/debug/style-packs/new?from={id}`。

「用此示例创建」：GET new 带 `from`，服务端取包，模板预填 examples，name=`{name}（副本）`，key 空。

生成页：`<select name="style_pack_id">` 空 option + 先 builtin 再用户包，label `名称（代号）`。校验失败回表单时保留选中值。`debug_generate` 把 `style_pack_id` 传入 `GenerateCaseDraftsCommand`。

- [ ] **Step 1: 写失败测试**

```python
def test_style_pack_list_shows_builtins(client):
    r = client.get("/debug/style-packs")
    assert r.status_code == 200
    assert "系统示例" in r.text
    assert "example.payment.api" in r.text
    assert "用此示例创建" in r.text

def test_generate_form_has_builtin_options(client):
    r = client.get("/debug/")
    assert r.status_code == 200
    assert "用例风格" in r.text
    assert "00000000-0000-4000-8000-000000000001" in r.text

def test_generate_with_builtin_shows_trace(client):
    r = client.post("/debug/generate", data={
        "text": "用户申请退款",
        "style_pack_id": "00000000-0000-4000-8000-000000000001",
    })
    assert r.status_code == 200
    assert "load_style_context" in r.text or "example.payment.api" in r.text

def test_copy_from_builtin_prefill(client):
    r = client.get("/debug/style-packs/new?from=00000000-0000-4000-8000-000000000001")
    assert r.status_code == 200
    assert "副本" in r.text
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/interfaces/web_debug/test_style_pack_pages.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现模板与路由**

表单 JS 最低要求：

- `addExample()` / `removeExample()` 上限 5  
- 每组 `addDraft()` 上限 3  
- 每用例 `addStep()`；新建用例默认 1 行步骤  
- 前置条件 textarea 按行拆分；标签按逗号拆分  
- `rationale` 用 `<details>`  
- 收集 DOM → JSON POST  

错误：API `issues` 展示在表单顶部，保留已填内容（失败时用 JS 不跳转；`fetch` 后若 400 显示 issues）。

`run_detail.html` 若 `run.style_pack` 非空，展示「风格包：名称（代号）」一行。

- [ ] **Step 4: 测试通过**

```bash
uv run pytest tests/interfaces/web_debug -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: 调试页支持维护与选择风格包。

EOF
)"
```

---

### Task 9: 文档与全量门禁

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`

- [ ] **Step 1: 更新文档（无单独红测，与规格第 10 节同步）**

README 增加：风格包调试入口 `/debug/style-packs`；生成可选风格；2 个系统示例；写 API 仅调试 UI；不是 RAG。

`architecture.md`：分层补 `style_pack`；明确「读始终 / 写随 debug」；非目标含向量检索。

- [ ] **Step 2: 全量门禁**

```bash
make lint && make typecheck && make test
```

Expected: 全绿

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs: 说明风格包能力与调试入口。

EOF
)"
```

---

## 规格覆盖自检

| 规格项 | 任务 |
| --- | --- |
| SP-001～005 维护页/可选/非空包 | 4, 8 |
| SP-006 key/id | 1, 5 |
| SP-007 CaseDraft 同一校验 | 1 |
| SP-008 5×3×15 | 1, 4 |
| SP-009 domain_hint | 6 |
| SP-010 Fake 忽略范文 | 6, 7 |
| SP-011 缺包 400 不建 Run | 7 |
| SP-012 读写挂载 | 5 |
| SP-013 调试走同一服务 | 8 |
| SP-014 PG JSONB | 3 |
| SP-015 合计字数 | 7 |
| SP-016 名称/下拉 | 1, 8 |
| SP-017 Run 快照 | 7 |
| SP-018 一组=1 需求+多用例 | 1 |
| SP-019 结构化表单 | 8 |
| SP-020 50 自建包 | 4 |
| SP-021 无导入导出 | 不实现 |
| SP-022 内置示例 | 2, 4, 5, 8 |
| README/architecture | 9 |

无 RAG、无 copy API、无鉴权：计划中未添加。
