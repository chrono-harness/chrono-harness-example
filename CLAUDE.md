# 仓库工作说明

工作前阅读本仓的[工具入口](.chrono-harness/USAGE.md)。产品职责见本仓 README。

## 本仓开发

业务实现位于 [`message.py`](message.py)，验收用例位于 [`check.py`](check.py)。修改业务后运行 `python3 -B check.py`。修改 CI 登记后运行 `sh .chrono-harness/ci/install.sh` 和 `sh .chrono-harness/ci/verify.sh`。
