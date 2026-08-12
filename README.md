# devspace-ai

通用测试域 AI 能力服务。v1 提供用例草稿生成（Case Draft Generation）同步 API 与本地调试页。

## 环境要求

- Python **3.12**
- [uv](https://github.com/astral-sh/uv)（包管理与运行）
- Docker（本地 PostgreSQL 16；可选一键起 api）

## 快速开始

```bash
cp .env.example .env
docker compose up -d db   # 主机端口 55432 → 容器 5432（避免与本机 5432 冲突）
make sync                 # uv sync --all-extras --frozen
make db-migrate
make run                  # http://127.0.0.1:8000
```

| 入口 | 说明 |
| --- | --- |
| 调试页 | [http://127.0.0.1:8000/debug/](http://127.0.0.1:8000/debug/) |
| 健康检查 | `GET /health` |
| 就绪检查 | `GET /ready`（需 PostgreSQL 可达） |
| OpenAPI | `/docs`、`/api/v1/...` |

## 模型配置与 Fake 默认行为

| 变量 | 说明 |
| --- | --- |
| `MODEL_API_KEY` | 为空时使用确定性 **Fake Model**（固定结构 2～3 条样例草稿，覆盖 `test_data` 空/非空） |
| `MODEL_BASE_URL` / `MODEL_NAME` | OpenAI 兼容网关地址与模型名 |
| `MODEL_PROVIDER` | 可显式设为 `fake` 或 `openai_compatible`；留空则按密钥自动推断 |

本地默认无需真实密钥即可跑通 Graph、API 与调试页。

## PostgreSQL 与查看数据

`.env.example` 默认：

```text
DATABASE_URL=postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai
```

- 用户 / 密码 / 库：`devspace` / `devspace` / `devspace_ai`
- 主机端口：**55432**（`docker-compose.yml` 映射 `55432:5432`；本机已有 5432 服务时不会冲突）
- 测试默认回退库名可为 `devspace_ai_test`（同实例）；CI 使用 service 的 `5432` 并注入 `DATABASE_URL`

用客户端连接同一串（去掉 SQLAlchemy 驱动前缀时用 `postgresql://...`）：

```bash
# psql（示例）
psql "postgresql://devspace:devspace@localhost:55432/devspace_ai"
# 查看 Run：SELECT run_id, status, created_at FROM generation_runs ORDER BY created_at DESC LIMIT 20;
```

DBeaver / DataGrip：主机 `localhost`，端口 `55432`，数据库 `devspace_ai`，用户/密码同上。

## Docker

```bash
make docker-up            # 构建并启动 api + db
# 或
docker compose up -d db   # 仅数据库
docker compose up -d --build
```

容器内 API 通过服务名 `db:5432` 连库；宿主机一律走 `localhost:55432`。

## 调试页开关（`ENABLE_DEBUG_UI`）

- `ENABLE_DEBUG_UI` 为空：按 `APP_ENV` 推断——`local` / `test` 开启，`prod` 关闭
- 显式 `true` / `false` 可覆盖推断
- 关闭时访问 `/debug/` 返回 404

## 常用命令

| 目标 | 说明 |
| --- | --- |
| `make sync` | `uv sync --all-extras --frozen` |
| `make lint` | ruff check + format --check |
| `make typecheck` | mypy strict |
| `make test` | pytest（需可达的 `DATABASE_URL`） |
| `make run` | Uvicorn 单 worker |
| `make docker-up` | compose 构建并启动 api + db |
| `make db-migrate` | Alembic upgrade head |

全量质量门禁（本地示例）：

```bash
export DATABASE_URL=postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai
uv sync --all-extras --frozen
make lint && make typecheck && make test
```

## 文档

- [架构说明](docs/architecture.md)
- [设计规格](docs/superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md)
- [实现计划](docs/superpowers/plans/2026-08-12-case-draft-generation.md)
