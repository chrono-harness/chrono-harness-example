# chrono-harness-example

这是一个独立的 Python 宿主。修改 message.py、check.py 或 message.txt 会触发 example 单元。修改 CI 配置会触发 harness 单元。GitHub Actions 用聚合检查报告结果，执行证据保留 1 天。

工具来自 [chrono-harness-main 的固定预览版](https://github.com/chrono-harness/chrono-harness-main/releases/tag/v0.1.0-alpha.1)。运行 `sh .chrono-harness/ci/install.sh` 安装。安装包下载到临时目录，用完即删。命令存放在工作树以外的共享目录，工作树仅创建可执行文件的符号链接。可用 CHRONO_EXAMPLE_INSTALL_ROOT 指定共享安装目录。

检查 Python 业务逻辑时运行 `python3 -B check.py`。验证 CI 配置和生成的工作流时运行 `sh .chrono-harness/ci/verify.sh`。
