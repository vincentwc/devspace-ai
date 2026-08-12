# PyCharm Debug 与 DDD 调用链

本文说明如何用 **Debug** 模式启动本服务，并按断点对照轻量 DDD 分层。

提供两套 Debug 配置，**优先使用真实模型**：

| 配置名 | 模式 | 何时用 |
| --- | --- | --- |
| **devspace-ai Debug (Model)**（默认） | 真实 OpenAI 兼容模型 | 有网关地址与 API Key 时 |
| **devspace-ai Debug (Fake)** | Fake Model | 无密钥、离线、或只想跟 Graph/落库链路 |

## 启动前准备

```bash
cp -n .env.example .env          # 若尚无 .env
docker compose up -d db
make sync
make db-migrate
```

确认 `.env` 中 `DATABASE_URL` 指向 `localhost:55432`（与 compose 一致）。

### 配置真实模型（推荐 Debug）

在 `.env` 中填写（示例）：

```text
MODEL_BASE_URL=https://your-gateway.example/v1
MODEL_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
MODEL_PROVIDER=openai_compatible
```

缺 `MODEL_API_KEY` 或 `MODEL_BASE_URL` 时，**Model** 配置会在启动阶段直接退出并提示改用 Fake。

## PyCharm 一键 Debug

1. **File → Open** 打开仓库根目录（含 `pyproject.toml`）。
2. **Settings → Project → Python Interpreter** 选项目下 `.venv`（`make sync` 后应已存在）。
3. **Run → Edit Configurations** 中选择：
   - 有模型：`devspace-ai Debug (Model)`（已设为默认）
   - 无模型：`devspace-ai Debug (Fake)`
4. 在源码中下断点（见下表）→ 点击 **Debug**（虫子图标），不要用带 `--reload` 的方式启动。
5. 浏览器打开 [http://127.0.0.1:8000/debug/](http://127.0.0.1:8000/debug/)，粘贴一段需求并提交。

命令行等价：

```bash
# 优先：真实模型（读 .env）
uv run python scripts/debug_server.py --mode model

# 备选：Fake
uv run python scripts/debug_server.py --mode fake
```

> **注意**：Debug 使用 `reload=False`、`workers=1`。`make run` 适合日常启动；跟断点请用上述配置。

## 分层一览（轻量 DDD）

| 层 | 路径 | 职责 |
| --- | --- | --- |
| 组合根 | `apps/api` | `create_app`：挂路由、注入 Model / Repository |
| 接口 | `interfaces/` | HTTP / Jinja ↔ `GenerateCaseDraftsCommand` |
| 应用 | `application/` | Graph 编排；依赖端口，不依赖 FastAPI/SQLAlchemy |
| 领域 | `domain/` | `CaseDraft` 校验、`RunStatus` 裁定 |
| 基础设施 | `infrastructure/` | 摄入、Fake/OpenAI、Postgres、配置 |

依赖方向：接口 → 应用 → 领域；基础设施实现出站端口，在组合根注入。

## 推荐断点（按一次生成请求顺序）

| 顺序 | 文件 | 位置 | 你在看什么 |
| --- | --- | --- | --- |
| 1 | `interfaces/web_debug/routes.py` 或 `interfaces/rest/routes_case_drafts.py` | `debug_generate` / `generate_case_drafts` | 接口层：Form → Command |
| 2 | `apps/api/main.py` | `create_app`（可选，仅启动时） | 组合根如何接线 |
| 3 | `application/case_generation/service.py` | `CaseGenerationService.generate` | 应用层入口与超时边界 |
| 4 | `infrastructure/source/text_ingest.py` | `ingest_text` / `ingest_upload` | 摄入与输入拒绝 |
| 5a | `infrastructure/model/openai_compatible.py` | `generate_case_drafts` | **Model** 模式：真实网关 |
| 5b | `infrastructure/model/fake_model.py` | `generate_case_drafts` | **Fake** 模式：本地样例 |
| 6 | `application/case_generation/service.py` | `_validate_raw` | 原始 JSON → 领域对象 |
| 7 | `domain/case_draft/models.py` | `CaseDraft.validate` | 领域不变量 |
| 8 | `domain/run/status.py` | `resolve_status` | succeeded / partial / failed |
| 9 | `infrastructure/persistence/pg_run_repository.py` | `save` | Run + payload 落库 |

有校验失败时，步骤 5～7 可能再走一轮（`repair_issues` 非空），然后才到 8～9。

## 调用链示意

```text
浏览器 / REST
  → interfaces（路由）
    → CaseGenerationService.generate
      → ingest（infrastructure）
      → ModelPort.generate_case_drafts（OpenAI Compatible 或 Fake）
      → CaseDraft.validate + resolve_status（domain）
      → [可选] 带 repair_issues 再调一次模型
      → RunRepository.save（Postgres）
  ← GenerationRunDTO / 调试页 HTML
```

## 常见问题

| 现象 | 处理 |
| --- | --- |
| Model 配置启动即退出（exit 2） | 检查 `.env` 的 `MODEL_API_KEY` / `MODEL_BASE_URL`，或改用 Fake 配置 |
| `ModuleNotFoundError: devspace_ai` | Interpreter 必须是项目 `.venv`，并先 `make sync` |
| `/ready` 503 | `docker compose up -d db` 后 `make db-migrate` |
| 断点不进业务代码 | 确认用的是 Debug 配置且无 reload；请求打到本进程的 8000 端口 |
| 没有调试页 | `APP_ENV=local` 或 `ENABLE_DEBUG_UI=true` |
| 想用真实模型却进了 Fake | 确认选的是 **Debug (Model)**，且未把 `MODEL_PROVIDER` 设为 `fake` |

更多架构背景见 [architecture.md](architecture.md)。
