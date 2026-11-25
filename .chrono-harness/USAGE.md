# chrono-harness/chrono-harness-example 工具入口

组件的用途、开发仓库和示例见 [Chrono Harness 用户与开发者入口](https://github.com/chrono-harness/chrono-harness-main)。

本仓是 Python 业务示例。业务代码和登记检查分别由 example 与 harness 单元验证。

开发分支为 `dev`，正式分支为 `main`。本仓选装 `cache`、`ci`、`diagnostics`、`distribution`、`harness`、`host-bootstrap`、`host-release`、`inputs`、`instructions`、`judge-ci`、`judge-cost`、`judge-filemap`、`judge-mixed`、`judge-projects`、`registration`、`judge-routes`、`judge-workflow`、`pr`、`test-git`、`worktree`、`verus`。

[组织协作规范](https://github.com/chrono-harness/chrono-harness-instructions/blob/dev/docs/contributing.md)

首次检出运行 `mise trust` 和 `mise run harness-setup`。本仓默认安装策略为 `pinned`。固定配方读取 [.config/mise/conf.d/chrono-harness.toml](../.config/mise/conf.d/chrono-harness.toml)。模板答案 `tool_versions` 可以按工具命令指定精确标签。临时运行 `CHRONO_TOOL_CHANNEL=preview mise run harness-setup` 会为已选组织工具安装各自最新测试版，也可以把 `preview` 换成 `stable` 或精确的 `v` 标签。再次运行普通安装即可恢复本仓选择。本仓 CI 的业务启动器按登记安装检查所需的工具。各分支、标签和 detached HEAD 使用相同规则。

刷新根指南使用 `mise run harness-setup`。`.chrono-harness/rules.json` 可用 `all` 配合 `exclude`，或 `only` 配合 `include` 逐项选择规则 ID，`off` 关闭继承。

用 `mise exec -- chrono-pr pr-reminders` 查看本地提醒，再运行 `mise exec -- chrono-pr pr-status --pr NUMBER --head-sha SHA` 查询 GitHub。

## 本仓验证

业务实现位于 [`message.py`](../message.py)，验收用例位于 [`check.py`](../check.py)。修改业务后运行 `python3 -B check.py`。修改 CI 登记后运行 `sh .chrono-harness/ci/install.sh` 和 `.chrono-harness/bin/chrono-ci verify --host-root . --config .chrono-harness/ci/units.json`。安装目录的测试入口是 `python3 -B .chrono-harness/ci/check-install-location.py`。
