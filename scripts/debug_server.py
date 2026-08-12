"""IDE Debug 入口：单进程、无 reload，便于 PyCharm 断点。

重要：在终端执行本脚本只会「普通启动服务」，不会挂上调试器。
要断点调试，请在 PyCharm 用 Debug（虫子）运行共享配置，而不是只跑 uv 命令。

两种模型模式（与是否挂调试器无关）：

    uv run python scripts/debug_server.py --mode model   # 需 .env 配置 MODEL_*
    uv run python scripts/debug_server.py --mode fake    # 强制 Fake，无需密钥

PyCharm 共享配置：
- 「devspace-ai Debug (Model)」→ --mode model + IDE 调试器
- 「devspace-ai Debug (Fake)」→ --mode fake + IDE 调试器
"""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from devspace_ai.infrastructure.config.settings import Settings


def _prepare_mode(mode: str) -> Settings:
    """按模式调整环境并校验，返回将用于启动的 Settings 快照（仅用于打印/校验）。"""
    if mode == "fake":
        # 覆盖 .env，确保不会误连真实网关
        os.environ["MODEL_PROVIDER"] = "fake"
        settings = Settings(_env_file=os.environ.get("ENV_FILE", ".env"))
        print("[debug] 模式=fake → FakeModelAdapter（不调用外部 LLM）", flush=True)
        return settings

    # model：优先真实 OpenAI 兼容网关
    os.environ.setdefault("MODEL_PROVIDER", "openai_compatible")
    settings = Settings(_env_file=os.environ.get("ENV_FILE", ".env"))
    if not settings.model_api_key or not settings.model_base_url:
        print(
            "[debug] 模式=model 需要在 .env 中配置 MODEL_API_KEY 与 MODEL_BASE_URL。\n"
            "  若暂时没有模型，请改用 PyCharm「devspace-ai Debug (Fake)」"
            " 或: uv run python scripts/debug_server.py --mode fake",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)
    print(
        f"[debug] 模式=model → OpenAICompatible"
        f"（base={settings.model_base_url!r}, name={settings.model_name!r}）",
        flush=True,
    )
    return settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="devspace-ai Debug 服务器")
    parser.add_argument(
        "--mode",
        choices=("model", "fake"),
        default="model",
        help="model=真实模型（默认）；fake=本地 Fake",
    )
    args = parser.parse_args(argv)
    _prepare_mode(args.mode)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(
        "[debug] 服务即将启动（单进程、无 reload）。\n"
        "  · 若你是在终端跑本命令：这只是普通启动，断点不会生效。\n"
        "  · 要断点：PyCharm 选择「devspace-ai Debug (Model/Fake)」后点虫子图标 Debug。\n"
        f"  · 启动后访问 http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}/debug/",
        flush=True,
    )
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
