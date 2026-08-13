# 贡献指南

## 分支与 PR

1. 从最新 `main` 开分支（`feat/` / `fix/` / `docs/` / `chore/`）。
2. 开发期间可用 `make hooks` 安装 pre-commit（提交时自动 ruff）。
3. 推送前：

   ```bash
   export DATABASE_URL=postgresql+psycopg://devspace:devspace@localhost:55432/devspace_ai
   make lint && make typecheck && make test
   ```

4. 开 PR 到 `main`，填写模板中的 Summary / Test plan。
5. 默认 **Squash merge**；合入后删除本地与远程功能分支，并 `git pull` 更新 `main`。

细则见 [`.cursor/rules/git-pr-workflow.mdc`](.cursor/rules/git-pr-workflow.mdc) 与 [docs/engineering-checklist.md](docs/engineering-checklist.md)。

## 何时用哪类流程

| 改动规模 | 建议 |
| --- | --- |
| 大功能 / 新 Capability | brainstorming →（需要时）grill-me → writing-plans → 实现 → verification → PR |
| Bug / 小 chore | 分支实现 → 门禁 → PR（可跳过 grill-me） |
| 仅文档 | `docs/` 分支 → PR |

## Debug 后

若在 PyCharm Debug 中改动了业务代码，提交前必须再跑相关测试或全量 `make test`，避免误改未提交进主干。

## Branch protection

仓库若为 Private + GitHub Free，可能无法开启 Branch protection。升级 Pro 或改为 Public 后，请为 `main` 开启：禁止直推、必须 PR、CI `quality` 通过后再合并。
