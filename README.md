# chrono-harness-example

这是一个独立的 Python 宿主。修改 message.py、check.py 或 message.txt 会触发 example 单元。修改 CI 配置会触发 harness 单元。GitHub Actions 用聚合检查报告结果，单元证据保留 1 天，聚合产物使用仓库的 GitHub Actions 保留期。

模板默认配置全部项目工具。运行 `mise trust` 和 `mise install` 安装本仓所选工具。示例的登记式检查使用其中八个命令，运行 `sh .chrono-harness/ci/install.sh` 会从相应工具仓的固定发行安装这八项，并在工作树内建立链接。可用 CHRONO_EXAMPLE_INSTALL_ROOT 指定工作树外的安装目录。

项目登记标明生产脚本与专属测试的语言。scoped CI 调用本仓安装的 projects 判官核对配对并执行选中的计划。projects 通过已安装的 routes 校验计划和执行回执。

检查 Python 业务逻辑时运行 `python3 -B check.py`。验证 CI 配置和生成的工作流时运行 `sh .chrono-harness/ci/verify.sh`。

## 本地任务工作树

工作树配置登记了 24 小时删除窗口。任务中的 Python 缓存、工具链接和中间状态都属于任务工作树，已安装的二进制位于共享安装目录。有长期用途的文件应在窗口内提交到 Git 或上传持久存储。工作树通过本仓安装链接调用固定版本的登记判官。本次工作树升级同时引入了 `registration_program` 配置项。回退到 bootstrap.1 时，随该工具的版本声明一起回退此配置项。清理程序同时读取本仓的 `.chrono-harness/retention.json`，回收新产生且已无使用方的工作树操作报告和维护清单。失败原件的诊断窗口为 24 小时。已有的未登记报告需核对具体使用方后处置。CI 任务随 GitHub 托管运行器回收。

### 为开发机的主检出启用定时清理

在长期保留的主检出中先运行 `sh .chrono-harness/ci/install.sh`。本机用户的定时器每小时调用一次 `.chrono-harness/bin/chrono-worktree maintain`。机器开机、用户调度服务在运行且目录可写时，即使无人再运行开发命令，维护也会检查到期工作树。活跃租约和待保全的工作由清理程序处理。

在 macOS 中将本仓的 launchd 配置安装到当前用户。以下命令从主检出根目录执行。每个路径拥有独立标签。

```sh
root=$(pwd -P)
label=org.chrono-harness.example-maintenance.$(printf %s "$root" | shasum -a 256 | cut -c1-16)
job="$HOME/Library/LaunchAgents/$label.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cp .chrono-harness/maintenance.launchd.plist "$job"
plutil -replace Label -string "$label" "$job"
plutil -replace Program -string "$root/.chrono-harness/bin/chrono-worktree" "$job"
plutil -replace WorkingDirectory -string "$root" "$job"
launchctl bootstrap "gui/$(id -u)" "$job"
```

删除或移动主检出前，使用同一组 `label` 和 `job` 变量，运行 `launchctl bootout "gui/$(id -u)/$label"` 和 `rm "$job"`。launchd 在下次用户登录后会加载仍已安装的配置。

在使用 systemd 用户服务的 Linux 开发机上，以下命令创建当前用户会话的小时定时器。重新建立用户服务会话后需要重新运行。卸载时运行 `systemctl --user stop "$unit.timer"`。

```sh
root=$(pwd -P)
unit=chrono-harness-example-maintenance-$(printf %s "$root" | sha256sum | cut -c1-16)
systemd-run --user --unit="$unit" --on-calendar=hourly \
  --working-directory="$root" "$root/.chrono-harness/bin/chrono-worktree" maintain
```
