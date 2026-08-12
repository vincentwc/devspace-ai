"""IDE Debug 入口：单进程、无 reload，便于 PyCharm 断点。

用法（推荐）：PyCharm 运行配置「devspace-ai Debug」，或：

    uv run python scripts/debug_server.py

启动前请确保 Postgres 已起且已迁移（见 docs/debug-pycharm.md）。
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    # 本机 Debug 默认绑 127.0.0.1；可用环境变量 HOST/PORT 覆盖
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "devspace_ai.apps.api.main:create_uvicorn_app",
        factory=True,
        host=host,
        port=port,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
