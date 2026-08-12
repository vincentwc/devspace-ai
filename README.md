# devspace-ai

通用测试域 AI 能力服务。v1 提供用例草稿生成（Case Draft Generation）同步 API 与本地调试页。

## 要求

- Python 3.12
- [uv](https://github.com/astral-sh/uv)
- Docker（本地 PostgreSQL 16）

## 快速开始

```bash
cp .env.example .env
docker compose up -d db
make sync
make db-migrate
make run
```

- 健康检查：`GET /health`
- 就绪检查：`GET /ready`（需 PostgreSQL 可达）
- OpenAPI：后续挂载于 `/api/v1`

## 常用命令

| 目标 | 说明 |
| --- | --- |
| `make sync` | `uv sync --all-extras --frozen` |
| `make lint` | ruff check + format --check |
| `make typecheck` | mypy strict |
| `make test` | pytest |
| `make run` | Uvicorn 单 worker |
| `make docker-up` | compose 构建并启动 api + db |
| `make db-migrate` | Alembic upgrade head |

## 文档

- [架构说明](docs/architecture.md)
- [设计规格](docs/superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md)
