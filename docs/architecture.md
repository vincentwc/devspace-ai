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
| 调试 UI | Jinja2（仅 local/test 或 `ENABLE_DEBUG_UI=true`） |
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

- `DATABASE_URL`：默认 `postgresql+psycopg://devspace:devspace@localhost:5432/devspace_ai`。
- `ENABLE_DEBUG_UI`：`None` 时按 `APP_ENV` 推断（`local`/`test` 开，`prod` 关）。
- 无模型密钥时使用确定性 Fake Model（后续任务实现）。

## 本地与 CI

```bash
docker compose up -d db
make sync
make db-migrate
make test
make run
```

CI 使用 `postgres:16` service，执行 lint → typecheck → migrate → pytest。

## 明确不做（v1）

写 TMS、鉴权、独立 SPA、SQLite。
