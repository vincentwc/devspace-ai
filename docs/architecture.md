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
application/      # 用例编排、端口
domain/           # CaseDraft / Run 不变量
infrastructure/   # 配置、日志、模型客户端、PostgreSQL 仓储
```

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

- [设计规格](superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md)
- [实现计划](superpowers/plans/2026-08-12-case-draft-generation.md)
- [仓库 README](../README.md)

## 明确不做（v1）

写 TMS、鉴权、独立 SPA、SQLite。
