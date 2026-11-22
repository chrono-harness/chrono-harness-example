# chrono-harness-example 使用说明

本仓是 Python 业务示例。业务代码和登记检查分别由 example 与 harness 单元验证。

开发分支为 `dev`。日常 PR 合入开发分支，正式版从 `main` 发布。

首次检出运行 `mise trust` 和 `mise run harness-setup`。工具版本见 [.config/mise/conf.d/chrono-harness.toml](../.config/mise/conf.d/chrono-harness.toml)。

开始任务时运行 `mise run harness-setup` 刷新根指南，成功后重新阅读本仓的 `AGENTS.md` 或 `CLAUDE.md`。完整规则和本仓开发步骤见根 [CLAUDE.md](../CLAUDE.md)。

用 `mise exec -- chrono-pr pr-reminders` 查看本地提醒，再运行 `mise exec -- chrono-pr pr-status --pr NUMBER --head-sha SHA` 查询 GitHub。

## 本仓验证

业务实现位于 [`message.py`](../message.py)，验收用例位于 [`check.py`](../check.py)。修改业务后运行 `python3 -B check.py`。修改 CI 登记后运行 `sh .chrono-harness/ci/install.sh` 和 `sh .chrono-harness/ci/verify.sh`。
