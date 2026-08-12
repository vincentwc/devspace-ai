#!/bin/sh
set -e
alembic upgrade head
exec uvicorn devspace_ai.apps.api.main:create_uvicorn_app \
  --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
