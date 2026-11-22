# chrono-harness-example

这是一个独立的 Python 宿主。修改 message.py、check.py 或 message.txt 会触发 example 单元。修改 CI 配置会触发 harness 单元。GitHub Actions 用聚合检查报告结果，执行证据保留 1 天。

模板默认配置全部项目工具。运行 `mise trust` 和 `mise install` 安装本仓所选工具。示例的登记式检查使用其中五个命令，运行 `sh .chrono-harness/ci/install.sh` 会从相应工具仓的固定发行安装这五项，并在工作树内建立链接。可用 CHRONO_EXAMPLE_INSTALL_ROOT 指定工作树外的安装目录。

检查 Python 业务逻辑时运行 `python3 -B check.py`。验证 CI 配置和生成的工作流时运行 `sh .chrono-harness/ci/verify.sh`。

## 本地任务工作树

工作树配置登记了 24 小时删除窗口。任务中的 Python 缓存、工具链接和中间状态都属于任务工作树，已安装的二进制位于共享安装目录。有长期用途的文件应在窗口内提交到 Git 或上传持久存储。运行 `.chrono-harness/bin/chrono-worktree maintain` 执行一轮维护。过期删除依赖宿主继续调用维护命令及当前租约释放。CI 任务随 GitHub 托管运行器回收。
