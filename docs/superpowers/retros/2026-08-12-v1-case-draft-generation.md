# Retro: v1 用例草稿生成闭环

## 做对了什么

- brainstorming + grill-me 先锁 DEC，再写 spec/plan
- Task 切片 + Fake 默认可跑，CI 能绿
- 后期用 verification-before-completion 对照 §13 验收

## 哪里不规范 / 浪费时间

- 一度在 `main` 上直接提交（注释/中文报错）
- PR 合入后分支上仍留后续 commit，差点漏合澄清文档
- Debug 时工作区误改曾导致 `has_text` 被注释掉

## 漏合、CI 红、误改根因

- Squash merge 后本地分支未删、未与 main 对齐
- `ruff format` 未进 pre-commit，CI 才发现
- Private Free 无法 Branch protection，缺少人为直推防线

## 下一轮要固定的习惯（最多 3 条）

1. 任意改动：分支 → `make lint && make typecheck && make test` → PR → squash → 删分支
2. `make hooks` 默认开启；宣称完成必须有新鲜门禁证据
3. 大需求结束填一份 retro；小 chore 可跳过 grill-me，不可跳过 PR
