.PHONY: sync lint typecheck test run docker-up db-migrate

sync:
	uv sync --all-extras --frozen

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

test:
	uv run pytest -v

run:
	uv run uvicorn devspace_ai.apps.api.main:create_uvicorn_app --factory --host 0.0.0.0 --port 8000 --workers 1

docker-up:
	docker compose up -d --build

db-migrate:
	uv run alembic upgrade head
