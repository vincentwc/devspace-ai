.PHONY: sync lint typecheck test hooks run docker-up db-migrate

sync:
	uv sync --all-extras --frozen

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

test:
	uv run pytest -v

# 安装 git pre-commit 钩子（ruff check --fix + ruff format）
hooks:
	uv run pre-commit install

run:
	uv run uvicorn devspace_ai.apps.api.main:create_uvicorn_app --factory --host 0.0.0.0 --port 8000 --workers 1

docker-up:
	docker compose up -d --build

db-migrate:
	uv run alembic upgrade head
