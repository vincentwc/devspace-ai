# 架构说明（v1）

## 目标

`devspace-ai` 提供通用测试域 AI 能力；v1 聚焦**用例草稿生成**（Case Draft Generation）：同步 API 接收需求文本/文件，经 LLM Graph 产出结构化用例草稿与 Run 轨迹。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 语言 / 包管理 | Python 3.12 + uv |
| API | FastAPI + Uvicorn（生产 `workers=1`） |
| 配置 | pydantic-settings |
| 持久化 | PostgreSQL 16 + SQLAlchemy 2（同步）+ Alembic + psycopg3 |
| 模型 | Fake（无密钥默认）/ OpenAI 兼容网关 |
| 调试 UI | Jinja2（`ENABLE_DEBUG_UI` / `APP_ENV` 门控，路径 `/debug/`） |
| 质量门禁 | ruff / mypy（strict）/ pytest + GitHub Actions（Postgres service） |

## 分层（轻量 DDD）

```text
apps/api          # 组合根：create_app、健康检查、路由挂载
interfaces/       # REST / 调试页适配
application/      # 用例编排、style_pack 服务、端口
domain/           # CaseDraft / Run / StylePack 不变量
infrastructure/   # 配置、日志、模型客户端、PostgreSQL 仓储、内置示例
```

### 风格包（Style Pack）

风格包在生成时可选注入范文，提升不同业务/风格的草稿质量。**不是 RAG**：按用户选定的包全文拼进提示词，不做向量检索。

| 路由 | 挂载策略 |
| --- | --- |
| `GET /api/v1/style-packs`（列表/详情） | **始终挂载** |
| `POST/PUT/DELETE /api/v1/style-packs` | **仅 `ENABLE_DEBUG_UI` 开启时**；关闭时同路径 stub 返回 404 |
| `/debug/style-packs`（维护页） | 随调试 UI 门控 |

内置 2 个系统示例包（支付接口、营销活动页）不入库、只读；用户自建包存 PostgreSQL `style_packs` 表（范文 JSONB）。选包生成时 Run payload 快照当时范文；调试页维护走同一 `StylePackService` 与 JSON API。

## 健康与就绪

- `GET /health`：进程存活。
- `GET /ready`：对 PostgreSQL 执行 `SELECT 1`；数据库不可达时返回 503。

## 配置要点

| 项 | 说明 |
| --- | --- |
| `DATABASE_URL` | 本地默认 `postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai`；compose 将主机 **55432** 映射到容器 5432（规避本机 5432 占用） |
| `ENABLE_DEBUG_UI` | `None` 时按 `APP_ENV` 推断（`local`/`test` 开，`prod` 关）；显式布尔可覆盖 |
| 模型 | 无 `MODEL_API_KEY` 时使用确定性 Fake Model；有密钥则走 OpenAI 兼容适配器 |

查看数据：用 `psql` / DBeaver / DataGrip 连接上述主机端口与库，查询 `generation_runs`（`payload` 为 JSONB）。

## 本地与 CI

```bash
cp .env.example .env
docker compose up -d db
make sync
make db-migrate
export DATABASE_URL=postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai
make test
make run
```

CI 使用 `postgres:16` service（宿主机 5432），注入 `DATABASE_URL`，执行 lint → typecheck → migrate → pytest；无真实模型密钥必须全绿。

## 相关文档

- [PyCharm Debug 与调用链断点](debug-pycharm.md)
- [设计规格](superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md)
- [实现计划](superpowers/plans/2026-08-12-case-draft-generation.md)
- [仓库 README](../README.md)

## 明确不做（v1）

写 TMS、鉴权、独立 SPA、SQLite、向量检索 / RAG、风格包导入导出。
