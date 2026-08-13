# 工程清单：验收与复盘

## A. 功能验收（每个 Milestone / 大 PR）

复制下表到 PR 或 issue，逐项勾选。机器项需附命令输出或 CI 链接。

| # | 项 | 类型 | 状态 |
| --- | --- | --- | --- |
| 1 | 主路径可演示（调试页或 API） | 人工 + 机器 | |
| 2 | `make lint && make typecheck && make test` 全绿 | 机器 | |
| 3 | CI `quality` 全绿 | 机器 | |
| 4 | 错误路径返回明确 `issues[].code`（若涉及） | 机器 | |
| 5 | Fake 默认可跑；真实模型（若声明支持）已手测 | 人工 | |
| 6 | Spec/Plan 偏差已写明 | 文档 | |

v1 用例草稿生成的权威验收见：  
[specs/2026-08-12-devspace-ai-case-generation-design.md §13](superpowers/specs/2026-08-12-devspace-ai-case-generation-design.md)。

## B. 合入后清理

```bash
git checkout main && git pull origin main
git branch -d <merged-branch>
git push origin --delete <merged-branch>   # 若远程仍在
```

## C. 复盘模板（大需求结束后填一份）

保存建议路径：`docs/superpowers/retros/YYYY-MM-DD-<topic>.md`

```markdown
# Retro: <topic>

## 做对了什么
-

## 哪里不规范 / 浪费时间
-

## 漏合、CI 红、误改根因
-

## 下一轮要固定的习惯（最多 3 条）
1.
2.
3.
```

## D. Autopilot 与无关 CI 失败

1. 先确认失败是否已在 `main` 复现。  
2. 若为最小格式/明显笔误且挡合入：可在当前 PR 带上「unblocking」修复，或先开 `fix/` 修主干。  
3. 不通过改 workflow 放宽检查来「变绿」。
