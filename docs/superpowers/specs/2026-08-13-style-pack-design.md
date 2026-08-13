# devspace-ai：用例风格包（Style Pack）设计

> 状态：已根据审阅决议更新，待确认后写实现计划  
> 日期：2026-08-13  
> 项目：`devspace-ai`  
> 前置规格：[2026-08-12 用例草稿生成](2026-08-12-devspace-ai-case-generation-design.md)  
> 结论先行：要提升「不同业务 / 不同风格」的生成质量，本轮做**可维护的范文风格包**，**不上 RAG**

本文中 **TMS** = 测试管理系统（如后续消费方 `cdp-suite`）。AI 只出草稿，不往 TMS 写库。

## 1. 文档目的

把「生成用例时按选定风格写」固化为可实施设计：在 `devspace-ai` 内维护带范文的风格包，生成时选用。本文是 implementation plan 与验收依据。

一句话理解：

- **风格包 = 带范文的文件夹**（例如「支付接口」「营销活动页」）
- **一组范文 = 一条需求 + 该需求下若干合格用例**
- 生成时选哪个文件夹，模型就按哪套范文写；不选则与现在完全一样

## 2. 背景与目标

### 2.1 问题

v1 只把**当次需求**和可选的一句话 `domain_hint` 送给模型。不同用户、不同测试系统、不同业务的用例写法差很大，模型不知道「这家」合格用例长什么样，草稿容易泛。

`domain_hint` 现状（本轮不改其语义）：

- 调试页「领域提示」可选输入，随生成请求传到模型
- 拼进 user 消息：需求正文后追加 `Domain hint: …`
- 无密钥时 Fake 模型**忽略**它；真实模型仅把它当口头提醒
- 不入库、无范文、不改 Graph

风格包用具体用例教模型，而不是靠一句话。

### 2.2 为何不是 RAG

「保存需求/用例样板」≠「知识库检索系统」。本轮样板数量小、由人指定用哪一包，不需要切分、向量库、按相似度召回。

库很大、人选不过来时，再把「按包取范文」换成检索实现；检索应发生在明确的语料上，而不是先做知识库产品。

### 2.3 目标

1. 调试站有独立页面：新建 / 编辑 / 删除风格包；**不能保存空包**。
2. 现有生成页增加「用例风格」下拉（可空）；选中后把该包范文注入提示词。
3. 运行轨迹能看出用了哪个包；该次 Run 的 payload 保存当时范文快照，包日后改删不影响回放。
4. `GET` 风格包列表/详情始终可用；生成可带 `style_pack_id`（供以后 TMS 接入）。
5. 不选包时，v1 生成行为不变。

### 2.4 非目标

- 向量检索 / 自动找相似用例
- 登录、权限、多租户隔离（同一环境内所有包可见、可读）
- 从 TMS 自动同步用例进包
- 风格包版本历史、导入/导出
- 生产环境专用管理后台（生产改包只能开调试 UI 或共用已有库，见 SP-021）
- TMS（`cdp-suite`）内的管理或生成界面
- 新的质检、归因等 Capability
- 独立 SPA

## 3. 已确认决策

| ID | 决策 |
| --- | --- |
| SP-001 | 样板作为 AI 服务内一等资产，有维护页；生成时点选风格 |
| SP-002 | 不上 RAG；只按用户选定的包注入范文 |
| SP-003 | 维护页与生成页都落在现有 `/debug/`（Jinja + 少量 JS，无登录） |
| SP-004 | 生成时风格包**可选**；不选 = v1 原路径 |
| SP-005 | 创建/保存时必须至少 1 组完整范文；不允许空包 |
| SP-006 | 包有 `id`（UUID，生成时用）和 `key`（稳定代号，创建后不可改） |
| SP-007 | 范文中的用例与生成结果同一套 `CaseDraft` 字段，走同一套领域校验 |
| SP-008 | 每包最多 5 条需求；每条需求下最多 3 条用例；合计最多 15 条用例 |
| SP-009 | `domain_hint` 保留；与风格包可同时使用；**写法以范文为准** |
| SP-010 | Fake 模型忽略范文（与忽略 `domain_hint` 一致）；看风格差异需真实模型 |
| SP-011 | 删除为真删；生成时包不存在 → 400 `PACK_NOT_FOUND`，不创建 Run、不调用模型 |
| SP-012 | 风格包 JSON API：`GET` 始终挂载；`POST/PUT/DELETE` **仅当调试 UI 开启时**挂载。生成仍为 multipart，增加可选 `style_pack_id` |
| SP-013 | 调试页调用与对外相同的 application 服务；维护页用 fetch 调 JSON API，禁止旁路实现 |
| SP-014 | PostgreSQL：`style_packs` 表 + 范文 JSONB |
| SP-015 | 当次需求文本 + **拼进提示词的范文字符**合计不超过 `max_text_chars`（默认 50k），超出拒绝 |
| SP-016 | 显示名 `name` 允许重复；必填，trim 后 1～80 字。下拉与列表展示 `名称（代号）`。`description` 选填，最多 500 字 |
| SP-017 | 选包生成时，Run 的 payload 快照 `id/key/name/examples`；未选包则省略该字段 |
| SP-018 | 一组范文 = 1 条需求 + 1～3 条合格用例 |
| SP-019 | 维护页全结构化表单（需求块 / 用例 / 步骤可增删），不手写 JSON；`rationale` 可选折叠 |
| SP-020 | 全环境最多 50 个风格包；超出新建 → `PACK_LIMIT` |
| SP-021 | 本轮不做导入/导出。生产默认不能写包；要改则临时 `ENABLE_DEBUG_UI=true` 或使用已有数据的库 |

## 4. 方案取舍

| 方案 | 要点 | 结论 |
| --- | --- | --- |
| 样板由 TMS 每次请求带上 | AI 不养内容 | 不选：要在 AI 侧可维护、可切换 |
| AI 内风格包 + 维护页 | 生成时选包 | **采纳** |
| 仓库内静态 YAML | 改样板要发版 | 排除 |
| 完整 RAG | 向量检索 | **排除本轮** |
| 读写 API 一律公开 | 实现最简单 | 排除：无登录时可被改/删包 |
| GET 公开、写仅调试 UI | 给 TMS 留读口，生产默认不能写 | **采纳（SP-012）** |
| 一组范文仅 1 条用例 | 表单更简单 | 排除：同一需求下需要多条用例 |
| 一组 = 1 需求 + 多条用例 | 5×3、合计 15 | **采纳（SP-008 / SP-018）** |
| 生成只记轨迹、不快照范文 | 实现省 | 排除：包改删后无法回放当时上下文 |
| Run payload 快照当时范文 | 与 v1 存需求原文同类 | **采纳（SP-017）** |
| 本轮做导入/导出 | 方便拷到生产 | 排除；生产维护见 SP-021 |

曾考虑「先建空文件夹再贴范文」：已否决。

## 5. 领域模型

### 5.1 风格包

| 字段 | 说明 |
| --- | --- |
| `id` | UUID |
| `key` | 稳定代号，如 `cdp.payment.api`；全局唯一；创建后不可改 |
| `name` | 显示名，如「支付接口」；可与其它包重名 |
| `description` | 可选，最多 500 字 |
| `examples` | 1～5 组范文（即 1～5 条需求） |
| `created_at` / `updated_at` | UTC |

`key`：非空；仅小写英文字母、数字、点、连字符；长度 1～64。  
`name`：必填；trim 后 1～80 字（按 Python `len` 计，含中文）。空格-only 视为空。

全环境包个数 ≤ 50。

### 5.2 一组范文

| 字段 | 说明 |
| --- | --- |
| `label` | 可选备注（如「退款成功」），最多 80 字 |
| `requirement_text` | 需求片段，trim 后非空 |
| `drafts` | 1～3 条合格 `CaseDraft` |

`CaseDraft` 与 v1 相同：`title`、`preconditions`、`steps`（`action` / `expected` / `test_data` 可空）、`priority`（`P0`–`P3` 或空）、`tags`、`rationale`（可空）。

### 5.3 不变量

- 至少 1 组范文；每组需求非空；每组 1～3 条通过 `CaseDraft.validate()` 的草稿
- 每包合计草稿 ≤ 15
- 编辑时删光范文再保存 → 拒绝，库中包不变
- 无版本号、无软删除、无租户字段

## 6. 页面

均在 `/debug/`，门控与 v1 相同。页头增加「风格包」链接（`/debug/style-packs`），生成页与风格包页可互达。

### 6.1 路由

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/debug/style-packs` | 列表：`名称（代号）`、需求条数、用例条数；新建 / 编辑 / 删除 |
| GET | `/debug/style-packs/new` | 新建表单 |
| GET | `/debug/style-packs/{id}/edit` | 编辑表单（代号只读） |
| GET | `/debug/` | 生成表单，含风格下拉 |

维护页提交：浏览器 fetch `POST/PUT/DELETE /api/v1/style-packs`（仅调试 UI 开启时这些写方法才存在）。删除前 `confirm`。

### 6.2 维护表单（结构化，不手写 JSON）

- 包：名称、代号（仅新建可填）、说明
- 「添加需求」（最多 5）：`label`、需求文本
- 需求块内「添加用例」（最多 3）：标题、优先级下拉（可空）、前置条件（textarea，一行一条）、标签（逗号分隔）、步骤表（操作 / 预期 / 测试数据，可加行）、`rationale` 可选折叠
- 新建一条用例时默认 **1 行空步骤**（保存时仍须有合法 action/expected）
- 校验失败：页面展示 `code` + `message` + `field` 路径，表单内容保留

### 6.3 生成页

- 下拉「用例风格」：第一项为空（不套风格）；其余 `名称（代号）`，值为 `id`
- 输入错误回表单时，保留已选 `style_pack_id`（与 v1 保留 `domain_hint` 相同）
- 不在生成页展开范文；`domain_hint` 保留

## 7. 生成链路

1. `ingest_requirement`：与 v1 相同
2. `load_style_context`（仅当 `style_pack_id` 非空）：  
   - 非法 UUID / 无法解析 → 400 `INVALID_INPUT`，不创建 Run  
   - 合法但包不存在 → 400 `PACK_NOT_FOUND`，不创建 Run、不调模型  
   - 包存在但 JSON 无法还原或校验失败 → 400 `INVALID_EXAMPLE`（或同等输入错误），不调模型  
   - 成功：记下快照，写入 trace  
3. 需求字符 + 范文块字符 > `max_text_chars` → 400 `INPUT_TOO_LONG`（message 含当前长度、上限、已计入风格包范文）
4. `generate_cases` / `validate_cases` / `persist_run`：与 v1 相同；payload 含 `style_pack` 快照（未选则无此键）

未选包：**不写** `load_style_context` 步。

选了包时 `summary` 固定风格：`支付接口（cdp.payment.api），需求 2 组，用例 4 条`。

### 7.1 提示词（真实模型）

`build_messages` 增加可选 `style_pack`。user 消息顺序：

1. 当次需求正文
2. 若有包：标题行 `Style pack: {name} ({key})`，随后每组 `Example N` + 需求片段 + 该组 `drafts` 的 JSON（字段与 `CaseDraft` 一致）
3. 若有 `domain_hint`：仍为 `Domain hint: …`

system 增加一句：用例结构、步骤粒度、用词**优先模仿范文**；范文不是要逐条复述的当次需求。

Fake 模型不读范文。单测断言 messages 含包名与范文需求原文。

## 8. API

前缀 `/api/v1`。

### 8.1 读（始终挂载）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/style-packs` | 列表，按 `updated_at` 倒序。每项：`id`、`key`、`name`、`description`、`requirement_count`、`draft_count`、`updated_at`。不含范文正文。某包 JSON 损坏时该项计数可为 0，**不**导致整表 500 |
| GET | `/style-packs/{id}` | 详情，含 `examples`。不存在 → **404** `{issues:[{code:PACK_NOT_FOUND,message}]}` |

列表不分页（有 SP-020 硬顶）。

### 8.2 写（仅 `debug_ui_enabled()` 为真时挂载）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/style-packs` | 创建。201 + 详情 body。body：`key`、`name`、`description?`、`examples`。`id` 服务端生成 |
| PUT | `/style-packs/{id}` | 整包更新 `name`、`description`、`examples`。schema `extra=forbid`，**不含 `key`**。不存在 → 404 `PACK_NOT_FOUND` |
| DELETE | `/style-packs/{id}` | 204 无 body。不存在 → 404 `PACK_NOT_FOUND` |

调试 UI 关闭时：写方法未挂载，表现为框架 404（与其它不存在路由相同），不另造错误码。

校验失败（创建/更新）：**400** `{issues:[…]}`。`issues[]` 可多项。`field` 路径示例：`name`、`examples[0].requirement_text`、`examples[1].drafts[0].steps[0].action`。

| code | 何时 |
| --- | --- |
| `EMPTY_PACK` | 范文组数为 0 |
| `INVALID_EXAMPLE` | 需求空、每组草稿数不为 1～3、或 `CaseDraft` 校验失败 |
| `INVALID_NAME` | 名称为空或超过 80 字 |
| `INVALID_KEY` | `key` 格式不合法 |
| `DUPLICATE_KEY` | `key` 已存在 |
| `PACK_LIMIT` | 需求 >5、单组用例 >3、合计用例 >15、或全环境包数 ≥50。message 写明是哪一种上限与当前值 |
| `PACK_NOT_FOUND` | 读/写/生成时 id 不存在 |
| `INVALID_INPUT` | 生成时 `style_pack_id` 非空但不是合法 UUID |
| `INPUT_TOO_LONG` | 需求 + 范文块超 `max_text_chars` |

`description` 超 500 字、`label` 超 80 字：`INVALID_INPUT`，`field` 指向该字段。

### 8.3 生成

`POST /api/v1/case-drafts/generate` 增加可选 `style_pack_id`。省略或空字符串 = 未选包。

响应：选了包时 `trace` 含 `load_style_context`；payload 回放经 `GET /api/v1/runs/{run_id}` 可见（在 `GenerationRunDTO` 增加可选 `style_pack` 快照对象，未选则为 `null` 或不输出；**推荐字段存在且未选为 `null`**，避免客户端猜键）。

## 9. 持久化

- 表 `style_packs`：`id`（PK，String 36）、`key`（unique）、`name`、`description`（可空）、`examples`（JSONB）、`created_at`、`updated_at`（timezone=True）
- Alembic 新迁移；与 `generation_runs` 同库
- `generation_runs.payload` 增加可选键 `style_pack`（快照对象）。旧行无此键，反序列化为「未选包」
- 生成加载时包数据非法 → 400，不当成无范文
- 并发：后写覆盖，不加锁

## 10. 分层与端口

- `domain/style_pack`：包与范文不变量（含 5×3、15、50、name/key 规则）
- `application`：Style Pack 维护服务；`CaseGenerationService` 依赖 `StylePackRepositoryPort`
- `StylePackRepositoryPort`：`list` / `get` / `create` / `update` / `delete` / `count`
- `infrastructure`：PostgreSQL 适配；`case_generation` 提示词增加范文块
- `interfaces`：读路由始终 include；写路由与 debug 页一同按 `debug_ui_enabled()` include

不引入向量库、embedding、独立检索服务。

实现本轮同步：`README.md`、`docs/architecture.md` 各增一小节（风格包、读/写挂载差异、非 RAG）。不改 CI 工作流。

## 11. 测试策略

| 层级 | 内容 |
| --- | --- |
| domain | 空包、5/3/15 上限、50 包上限、`key`/`name` 规则、范文 `CaseDraft` 校验 |
| application | 选包则 messages 含范文；不选则无范文块；缺包不调模型；超长拒绝；payload 含快照 |
| persistence | 读写往返；删后 get 空；`key` 唯一；旧 Run 无 `style_pack` 键仍能反序列化 |
| REST | GET 始终可测；写接口在 debug 关闭时 404；开启时可 CRUD；generate 带/不带 id |
| 调试页 | 无范文保存失败；列表 `名称（代号）`；生成下拉可选；轨迹含包名；互链 |
| Fake / CI | 无密钥全绿；不要求 Fake 输出随包变化 |

## 12. 验收标准

1. 调试站能建/改/删风格包；结构化表单可添加需求与用例；无完整范文则存不进去，并指出路径。
2. 生成页下拉为 `名称（代号）`；选中后轨迹含包名、需求组数、用例条数；`GET` 该 Run 可见范文快照。
3. 不选包时生成行为与 v1 一致（无 `load_style_context`，`style_pack` 为 null）。
4. `GET /api/v1/style-packs` 在关闭调试 UI 时仍可用；此时 POST 风格包为 404。
5. 删除后再用该 id 生成 → 400 `PACK_NOT_FOUND`，未调模型、未建 Run。
6. 无真实密钥时 `make lint && make typecheck && make test` 全绿。

## 13. 后续（不在本轮）

- `cdp-suite`：拉包列表、生成时传 `style_pack_id`
- 鉴权与按系统隔离；生产可写的管理面
- 导入/导出
- 从已确认入库的用例沉淀进包
- 包太多无法点选时再评估检索（Graph 上的 Tool，不是先做知识库产品）

## 14. 开放问题（已关闭）

| 问题 | 决议 |
| --- | --- |
| 先做 RAG 还是先做样板？ | 先做显式风格包 |
| 样板在 TMS 还是在 AI？ | 在 AI，有维护页 |
| 生成时包是否必选？ | 可选 |
| 是否允许空包？ | 不允许 |
| 维护页做正式后台还是调试页？ | `/debug/`，本轮不做登录 |
| 写 API 是否与生成一样始终公开？ | 否；仅调试 UI 开启时挂载写方法 |
| 一组范文几个需求、几个用例？ | 每包最多 5 条需求，每条最多 3 条用例，合计 15 |
| 维护表单？ | 全结构化，不手写 JSON |
| 显示名能否重名？ | 能；下拉 `名称（代号）` |
| 生产如何改包？ | 本轮不导入导出；开调试 UI 或共用已有库 |
| 环境内最多几个包？ | 50 |
| Run 是否快照范文？ | 是 |

## 15. Ambiguity Report

> grill-me Spec 模式审阅（阈值 0.2）；决议已写回 SP-008、SP-012、SP-016～SP-021 及第 6～8 节。

```
Ambiguity Report:
  Goals:        0.0   ✓ clear
  Acceptance:   0.25  ✓ mostly clear
  Boundaries:   0.0   ✓ clear
  Alternatives: 0.0   ✓ clear
  Assumptions:  0.25  ✓ mostly clear
  ──────────────────────────────
  Aggregate:    0.10  ✓ below threshold (0.2 spec)

Push lightly on: prompt 质量仍属真实模型效果（Fake 不随包变，不阻塞本轮）；50k 按拼进提示词的字符计。
```
