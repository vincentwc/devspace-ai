# devspace-ai：需求 → 用例草稿生成（瘦 Agent）设计

> 状态：已确认设计稿  
> 日期：2026-08-12  
> 项目：`devspace-ai`  
> 首个消费方（后续）：`cdp-suite`（`/Users/vincent/developEnv/code/cestc/cdp-suite`）  
> 关联背景：测试管理系统 AI 能力通用化；首版完成可演示闭环，再扩展其他能力与业务系统

## 1. 文档目的

本文将「测试管理 + AI」的首个闭环固化为可实施设计：在独立项目 `devspace-ai` 中建设通用 AI 能力服务；v1 交付「需求文本 → 结构化用例草稿」，并采用可演进到 Agent 平台的瘦工作流形态。

本文是后续 implementation plan 与开发验收的依据。

## 2. 背景与目标

### 2.1 背景

- `cdp-suite` 已具备测试资产、测试环境等业务能力（轻量 DDD / Java），当前缺少 AI 能力。
- 希望 AI 能力**不绑定**单一业务系统，后续可对接其他测试业务系统。
- 因此新建 `devspace-ai` 作为通用 AI 服务，而不是把模型调用直接写进 `cdp-suite`。

### 2.2 产品定位

| 维度 | 决策 |
| --- | --- |
| 长期愿景 | Agent 工作流平台（多能力：生成、质检、归因、报告等） |
| v1 形态 | 可演进的瘦 Agent：固定多步 Graph + Tool 端口 |
| 首个能力 | 需求 → 用例草稿生成（创造资产） |
| 成功标准 | 调试页内完成端到端演示闭环 |

### 2.3 v1 目标

1. 用户在调试页粘贴或上传需求文本，得到结构化 `CaseDraft[]`。
2. 可查看 Graph 执行轨迹，并可按 `run_id` 回放。
3. 对外 API 与领域模型与具体 TMS 无关，便于后续系统接入。
4. 模型通过 OpenAI 兼容协议配置接入，不绑定单一厂商 SDK。

### 2.4 v1 非目标

- 不写入 `cdp-suite` 或其他 TMS（由业务系统在人工确认后自行入库）
- 不生成「测试项 → 测试需求 → 用例」整树；只生成用例列表
- 不解析 `docx/pdf`（可列为后续小步）
- 不对接外部需求系统（预留 `RequirementSource` 端口）
- 不做完整 Agent 操作系统（自治路由、多 Agent 注册中心、长期记忆）
- 不做鉴权、多租户、正式业务前端
- 不实现用例质量评审能力（下一 Capability 候选）

## 3. 已确认决策

| ID | 决策 |
| --- | --- |
| DEC-001 | 首版主路径：需求 → 用例草稿（创造资产）；质量评审后置 |
| DEC-002 | 需求输入：v1 粘贴/上传；抽象 `RequirementSource`，预留外部需求系统 |
| DEC-003 | AI 服务只返回草稿；业务系统负责预览确认与入库 |
| DEC-004 | 生成物层级：仅用例列表，挂载到业务侧已选测试需求（业务侧后续集成时处理） |
| DEC-005 | 首个可演示闭环落在 `devspace-ai` 调试页 |
| DEC-006 | 技术栈：Python + FastAPI |
| DEC-007 | 模型接入：OpenAI 兼容 `base_url + api_key + model` |
| DEC-008 | 架构姿态：愿景=Agent 平台；v1=固定 Graph 瘦 Agent，预留 Tool/Capability 扩展 |
| DEC-009 | 代码结构：轻量 DDD + 六边形（Ports & Adapters） |
| DEC-010 | 测试步骤字段包含可空 `test_data` |
| DEC-011 | 生成 API 同步阻塞：请求等到 Graph 结束（或超时）再返回完整 `drafts`/`trace`；对外状态不含 `queued` |
| DEC-012 | Run 状态：全部通过 → `succeeded`；≥1 条可用 → `partial`；0 条可用 → `failed` |
| DEC-013 | 超长输入直接拒绝（默认 50k 字符，可配置）；错误信息明确说明原因与当前上限 |
| DEC-014 | `max_cases` 默认 10，硬顶 30；超硬顶明确 4xx |
| DEC-015 | 分层超时：模型默认 120s，HTTP 总超时默认 150s（均可配置）；超时 → `failed` 并落库失败 Run |
| DEC-016 | 统一 `issues[]: { code, message, draft_index?, field? }`；4xx 与 failed/partial 共用 code+message 风格 |
| DEC-017 | 无密钥或 `MODEL_PROVIDER=fake` 时使用确定性 Fake Model，仍走完整 Graph |
| DEC-018 | 调试页：FastAPI + Jinja + 少量原生 JS；无独立前端构建 |
| DEC-019 | 生成接口统一 `multipart/form-data`；`text`/`file` 恰好二选一 |
| DEC-020 | 上传默认上限 1 MiB（可配置）；超出明确 4xx |
| DEC-021 | `tags` 类型为可选字符串列表 |
| DEC-022 | 持久化使用 PostgreSQL 16（不再使用 SQLite）；SQLAlchemy 2.0 同步 + Alembic + psycopg3 |
| DEC-023 | Run 存储：`generation_runs` 表，核心列 + `payload JSONB` |
| DEC-024 | 调试页默认仅 local/test 开启；生产需 `ENABLE_DEBUG_UI=true` 才挂载 |
| DEC-025 | 生产 Uvicorn 单 worker；CI/本地测试使用 Postgres service/compose |

## 3.1 方案取舍

曾比较三种架构：

| 方案 | 要点 | 结论 |
| --- | --- | --- |
| 1. 能力插件式瘦服务 | 稳定 API + Capability 插件 | v1 形态采纳（固定 Graph 实现首个 Capability） |
| 2. TMS 适配器中枢 | AI 服务内维护各系统字段映射/写入 | **排除**：易绑死首个 TMS，与「只返回草稿」冲突 |
| 3. 完整 Agent 平台 | 多 Agent 路由、注册中心、长期记忆 | **愿景采纳，v1 排除直接落地**：过重；v1 用可演进瘦 Graph，对外契约稳定后再升级编排 |

最终姿态：**愿景 = 方案 3；v1 = 方案 1 形态的可演进瘦 Agent（同步 API、只出 `CaseDraft`）**。

## 4. 架构

### 4.1 系统位置

```text
[调试页 / 未来业务系统]
        │  HTTP (OpenAPI)
        ▼
   devspace-ai (FastAPI)
        │
        ├─ interfaces：REST + web_debug
        ├─ application：用例编排（固定 Graph）
        ├─ domain：Run / Requirement / CaseDraft / Capability
        ├─ infrastructure：Model / Source / Persistence / Prompt
        └─ Model Gateway（OpenAI-compatible）
```

`cdp-suite` 不在 v1 闭环内写库。v1 闭环在 `devspace-ai` 内完成：输入需求 → 跑工作流 → 调试页展示轨迹与草稿。

### 4.2 为何采用轻量 DDD

适合进入领域层的概念具备状态或不变量：

- `GenerationRun` 生命周期与轨迹
- `CaseDraft` / 步骤校验规则
- `RequirementDocument` 规范化结果
- Capability / Tool 边界

提示词拼装、LLM HTTP、文件 IO、调试页属于 application / infrastructure，不为「每一次模型调用」强造重聚合。

### 4.3 包结构

```text
devspace-ai/
├── apps/
│   └── api/                    # 启动入口、依赖组装
├── interfaces/
│   ├── rest/                   # FastAPI routes / HTTP DTO
│   └── web_debug/              # 调试页（调用同一 application 用例）
├── application/
│   ├── case_generation/        # 用例生成应用服务
│   ├── port/
│   │   ├── inbound/            # GenerateCaseDraftsPort 等
│   │   └── outbound/           # ModelPort / RequirementSourcePort / RunRepositoryPort
│   └── dto/                    # 应用层命令与结果
├── domain/
│   ├── run/                    # GenerationRun、RunStatus、RunTrace、StepRecord
│   ├── requirement/            # RequirementDocument、RequirementSourceType
│   ├── case_draft/             # CaseDraft、TestStep、校验不变量
│   └── capability/             # CapabilityId、固定工作流定义
├── infrastructure/
│   ├── model/                  # OpenAI-compatible adapter
│   ├── source/                 # Paste/Upload；预留外部需求源
│   ├── persistence/            # Run/Trace（v1：PostgreSQL + SQLAlchemy/Alembic）
│   └── prompt/                 # 模板加载与渲染
└── tests/
```

依赖方向：

```text
interfaces → application → domain
infrastructure → application.port / domain
禁止：domain → infrastructure / interfaces
```

### 4.4 演进关系

- v1：`application/case_generation` 编排固定 Graph：`ingest → generate → validate`。
- 后续：新增 Capability（如 `case_review`）或将 Graph 升级为可配置 Agent，**不修改** `CaseDraft` 主契约与 `GenerateCaseDraftsPort` 语义。
- 需求来源通过 `RequirementSourcePort`：v1 = paste/upload；日后 = 外部系统适配器。

## 5. 领域模型与数据契约

### 5.1 RequirementDocument

| 字段 | 说明 |
| --- | --- |
| `source_type` | `paste` \| `upload` \|（预留）`external` |
| `title` | 可选 |
| `text` | 规范化后的纯文本 |
| `metadata` | 文件名、字数等；不作为核心业务规则输入 |

### 5.2 CaseDraft

| 字段 | 约束 |
| --- | --- |
| `title` | 必填，非空 |
| `preconditions` | 可选，字符串列表 |
| `steps[]` | 至少 1 项 |
| `priority` | 可选：`P0` \| `P1` \| `P2` \| `P3` |
| `tags` | 可选，字符串列表 |
| `rationale` | 可选，便于人工确认 |

### 5.3 TestStep

| 字段 | 约束 |
| --- | --- |
| `action` | 必填，非空 |
| `expected` | 必填，非空 |
| `test_data` | 可空；API 输出统一为 `null`（空字符串在进入领域时规范为 `null`） |

生成提示要求：仅在需求中存在明确数据（账号、边界值、样例输入等）时填写 `test_data`；否则为 `null`，不强造。

### 5.4 GenerationRun

| 字段 | 说明 |
| --- | --- |
| `run_id` | 唯一标识 |
| `status` | `running` \| `succeeded` \| `failed` \| `partial`（对外不同步暴露 `queued`） |
| `input` | 输入摘要/正文（受长度上限约束） |
| `drafts` | 通过校验的 `CaseDraft[]` |
| `trace.steps[]` | 每步名称、起止时间、摘要、token、错误 |
| `issues[]` | `{ code, message, draft_index?, field? }` |
| `error` | 可选；与首要 issue 对齐的人类可读摘要 |

状态判定：

- 全部草稿通过校验 → `succeeded`
- 至少 1 条可用草稿且存在未通过/纠错残留问题 → `partial`
- 0 条可用草稿（含模型失败、超时、全员校验失败）→ `failed`

### 5.5 对外 API

#### `POST /api/v1/case-drafts/generate`（同步）

- Content-Type：`multipart/form-data`
- 字段：`text`（可选）、`file`（可选）、`language`（默认 `zh-CN`）、`max_cases`（默认 10，硬顶 30）、`domain_hint`（可选）
- 校验：`text` 与 `file` 必须恰好提供其一；否则 4xx，`issues/code+message` 说明原因
- 行为：阻塞至 Graph 完成或总超时；响应包含 `run_id`、`status`、`drafts`、`trace`、`issues`
- 超长文本（默认 >50k 字符）或超大文件（默认 >1 MiB）：不调用模型，直接 4xx，明确原因与当前上限

#### `GET /api/v1/runs/{run_id}`

- 回放结果与轨迹（含失败/超时已落库的 Run）

API 使用 OpenAPI 描述；HTTP DTO 与 domain 对象分离，映射发生在 `interfaces` 层。

### 5.6 错误与 issues 约定

| 场景 | HTTP | status（若已创建 Run） | 示例 code |
| --- | --- | --- | --- |
| 未提供 text/file 或同时提供 | 400 | （无 Run 或未执行） | `INVALID_INPUT` |
| 文本超长 | 400 | — | `INPUT_TOO_LONG` |
| 文件过大 / 类型不支持 | 400 | — | `FILE_TOO_LARGE` / `UNSUPPORTED_FILE_TYPE` |
| `max_cases` 超硬顶 | 400 | — | `MAX_CASES_EXCEEDED` |
| 模型超时 | 200（已落库失败 Run，便于回放） | `failed` | `MODEL_TIMEOUT` |
| 无可用草稿 | 200 | `failed` | `NO_VALID_DRAFTS` |
| 部分可用 | 200 | `partial` | `DRAFT_VALIDATION_FAILED` 等 |

## 6. 主流程（固定瘦 Agent Graph）

```text
1. ingest_requirement
   - multipart text/file → RequirementDocument
   - 超长/超大：直接拒绝（不进模型）；合法输入进入后续步骤
2. generate_cases
   - ModelPort（真实兼容网关或 Fake）+ 提示词 → 原始结构化输出
   - 反序列化为 CaseDraft 候选
3. validate_cases
   - 领域校验
   - 失败则带错误反馈再生成一次（最多 1 次）
   - 按 DEC-012 判定 succeeded / partial / failed，填充 issues[]
4. persist_run
   - 保存 Run + Trace + issues（含超时失败），供调试页回放
```

应用层只负责编排；领域负责草稿合法性与 Run 状态迁移；基础设施负责 LLM、文件与存储。  
同步语义：`POST /generate` 在步骤 1–4 完成后返回（或总超时后返回已落库的失败 Run）。

## 7. 调试页

调试页属于 `interfaces/web_debug`，技术选型为 **FastAPI + Jinja + 少量原生 JS**（无独立前端构建）。必须调用与对外相同的 application/API，禁止旁路实现。

v1 能力：

1. 输入：粘贴文本；上传 `txt` / `md`（≤1 MiB）
2. 选项：语言、用例数量上限（默认 10）、领域提示
3. 触发生成：同步调用 `POST /api/v1/case-drafts/generate`（multipart）
4. 结果：用例卡片（含 `test_data`）、一键复制 JSON；展示 `issues`
5. 轨迹：`ingest → generate → validate` 的状态与摘要
6. 历史：按 `run_id` 查看最近 Run（含失败/超时）

非目标：登录、权限、多租户、编辑后回写业务库、独立 SPA。  
挂载条件：仅 `APP_ENV=local|test` 或 `ENABLE_DEBUG_UI=true` 时启用 `/debug/`；生产默认关闭。

## 8. 可观测性与配置

### 8.1 Run 级观测

| 维度 | 内容 |
| --- | --- |
| 业务轨迹 | `step_name/status/started_at/ended_at/summary/error` |
| 模型用量 | `model`、`prompt_tokens`、`completion_tokens`（网关若返回） |
| 质量信号 | 生成条数、校验失败条数、是否触发 validate 重试 |
| 关联 ID | `run_id` 贯穿日志与 API |

原则：

- 应用层写 `RunTrace`；基础设施落库/打日志
- 提示词全文默认不写普通日志（可配置 debug）；默认保留 hash/长度/摘要
- 模型适配器：超时 + 有限重试（仅网络/5xx）
- 业务校验重试：仅 validate 步，最多 1 次

### 8.2 配置项

| 配置 | 默认 | 用途 |
| --- | --- | --- |
| `MODEL_BASE_URL` | — | 兼容网关地址 |
| `MODEL_API_KEY` | — | 密钥（环境变量，不入库） |
| `MODEL_NAME` | — | 模型名 |
| `MODEL_PROVIDER` | 无密钥时视为 `fake` | `openai_compatible` / `fake` |
| `DATABASE_URL` | — | PostgreSQL 连接串（必填，非测试假值） |
| `ENABLE_DEBUG_UI` | 随 `APP_ENV` | `local`/`test` 默认开；`prod` 默认关，显式 `true` 才挂载 `/debug/` |
| 文本长度上限 | 50k 字符 | 超出拒绝 |
| 上传大小上限 | 1 MiB | 超出拒绝 |
| `max_cases` 默认 / 硬顶 | 10 / 30 | 请求未传时用默认；超硬顶拒绝 |
| 模型调用超时 | 120s | 仅网络/模型等待 |
| HTTP 总超时 | 150s | 含 ingest/validate/persist |

### 8.3 持久化（PostgreSQL）

- 引擎：PostgreSQL 16
- 访问：SQLAlchemy 2.0（同步 Session）+ Alembic 迁移 + psycopg3
- 表：`generation_runs`  
  - 列：`run_id`（PK）、`status`、`created_at`、`input_text`、`payload`（JSONB：drafts/trace/issues/error 等）
- 部署：v1 单实例应用 + 独立 Postgres；Uvicorn `workers=1`
- 查看数据：`psql` / DBeaver / DataGrip 连接 `DATABASE_URL`

## 9. 与业务系统的衔接（非 v1 实现）

1. `devspace-ai` 始终返回 `CaseDraft[]`。
2. 未来 `cdp-suite`（或其他 TMS）：用户选定测试需求 → 调用 AI → 预览 → 调用现有创建用例接口批量入库。
3. 字段映射表留在业务系统防腐层，不进入 `devspace-ai` domain。

## 10. 测试策略

| 层级 | 内容 | 方式 |
| --- | --- | --- |
| domain | `CaseDraft` 不变量（含 `test_data` 可空）、Run 状态迁移 | 纯单元测试 |
| application | Graph 编排、校验失败重试、partial 行为 | Mock outbound ports |
| infrastructure | OpenAI 兼容请求形状、错误映射、txt/md 读取 | 契约测试 / fake server（可选） |
| interfaces | 入参校验、DTO 映射、调试页关键路径 | APITestClient |
| 冒烟 | 真实网关手工验证 | optional，不进默认 CI |

默认 CI 在无真实模型密钥时必须全绿（使用确定性 Fake Model：固定结构 2～3 条样例草稿，覆盖 `test_data` 空/非空，仍走完整 Graph）。

## 11. 里程碑

| 里程碑 | 交付 |
| --- | --- |
| M1 骨架 | DDD 分层、端口、配置、健康检查、PostgreSQL/Alembic、Run 持久化 |
| M2 生成闭环 | Fake/真实模型均可跑通 Graph；API 返回合法 `CaseDraft` |
| M3 调试页 | 粘贴/上传 → 结果 + 轨迹 + 回放（**首个闭环验收点**） |
| M4 硬化 | 限制项、错误码、测试与 README |

M3 完成后，另开迭代：

- `cdp-suite` 适配（预览确认入库），或
- 下一个 Capability（如用例质检）

## 12. 风险与对策

| 风险 | 对策 |
| --- | --- |
| 模型输出不稳定/非 JSON | 强 schema 提示 + validate 一次纠错；失败返回 partial |
| 需求文本过长 | 可配置上限，默认拒绝并返回明确 4xx |
| 过早做成重 Agent 平台 | 固定 Graph + Tool 端口；平台化进后续里程碑 |
| 被单一 TMS 模型绑死 | 领域只认 `CaseDraft`；映射留在业务系统 |
| 无网关无法演示 | Fake Model + 固定样例，保证本地与 CI |

## 13. 验收标准

1. 调试页（Jinja）完成同步闭环：粘贴或上传 `txt/md` → 得到符合 `CaseDraft` schema 的草稿 → 可见轨迹与 `run_id` 回放。
2. OpenAPI 稳定；步骤含可空 `test_data`；错误与 partial 均返回 `issues[].code/message`。
3. 无真实密钥时 Fake Model + 默认 CI 全绿；配置兼容网关后可切真实模型。
4. 超长文本 / 超大文件 / 非法 multipart 返回明确 4xx 原因。
5. 状态机符合 DEC-012；超时落库失败 Run 可回放。
6. 新增 Capability/Tool 时无需修改 v1 对外主契约语义。

## 14. 开放扩展点（已选型，不阻塞 v1）

- `RequirementSourcePort` 的 `external` 实现
- `docx/pdf` 文本抽取
- `case_review` Capability
- Graph → 可配置多 Agent 编排
- 业务系统侧批量入库适配器（`cdp-suite` 优先）

## 15. Ambiguity Report

> grill-me Spec 模式审阅（阈值 0.2）；决议已写回 DEC-011～DEC-025。  
> 实现计划审阅追加：持久化由 SQLite 调整为 PostgreSQL（DEC-022～025）。

```
Ambiguity Report:
  Goals:        0.0   ✓ clear
  Acceptance:   0.25  ✓ mostly clear
  Boundaries:   0.0   ✓ clear
  Alternatives: 0.0   ✓ clear
  Assumptions:  0.25  ✓ mostly clear
  ──────────────────────────────
  Aggregate:    0.10  ✓ below threshold (0.2 spec)

Push lightly on: prompt 质量无法机器强验收（属模型效果，不阻塞 v1）。
```
