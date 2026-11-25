# chrono-harness-example

这是一个独立的 Python 宿主。修改 message.py、check.py 或 message.txt 会触发 example 单元。修改 CI 配置会触发 harness 单元。GitHub Actions 用聚合检查报告结果，单元证据保留 1 天，聚合产物使用仓库的 GitHub Actions 保留期。

模板默认配置全部项目工具。运行 `mise trust` 和 `mise install` 安装本仓所选工具。示例的登记式检查使用其中八个命令，运行 `sh .chrono-harness/ci/install.sh` 会从相应工具仓的固定发行安装这八项，并在工作树内建立链接。可用 CHRONO_EXAMPLE_INSTALL_ROOT 指定工作树外的安装目录。

项目登记标明生产脚本与专属测试的语言。scoped CI 调用本仓安装的 projects 判官核对配对并执行选中的计划。projects 通过已安装的 routes 校验计划和执行回执。

检查 Python 业务逻辑时运行 `python3 -B check.py`。验证 CI 配置和生成的工作流时运行 `.chrono-harness/bin/chrono-ci verify --host-root . --config .chrono-harness/ci/units.json`。安装目录的测试入口是 `python3 -B .chrono-harness/ci/check-install-location.py`。

## 选用完整治理示例

`dev` 默认按业务变更选择检查。可选的 `profile/full` 分支在同一 Python 业务上登记七个判官、输入声明和集成证明。支持 macOS 26 arm64 和 Ubuntu 24.04 x86_64。要查看已验收配置，从本仓检出运行以下命令。

```sh
git fetch origin profile/full
git show a2ef667c0424b61321b2b724ea3c2916b2155fca:.chrono-harness/config.json
```

在选用该配置的开发工作树中，使用 mise 和 `sh .chrono-harness/ci/install.sh` 将发行程序安装到工作树外。验收配方从已登记的基线和候选采集输入，在工作树中运行 `.chrono-harness/bin/chrono-harness check` 签发集成证明，并再次运行同一入口验证交付。每个平台的检查结果、证书摘要和实际执行程序数可查原始作业日志。[固定配置](https://github.com/chrono-harness/chrono-harness-example/tree/a2ef667c0424b61321b2b724ea3c2916b2155fca) · [可复现的完整命令](https://github.com/chrono-harness/chrono-harness-example/blob/3ee748be9379692b4ebbc6a40b4a9ff5ce2e387c/.github/full-native.py) · [双平台落地检查](https://github.com/chrono-harness/chrono-harness-example/actions/runs/45385225764)

## 本地任务工作树

工作树配置登记了 24 小时删除窗口。任务中的 Python 缓存、工具链接和中间状态都属于任务工作树，已安装的二进制位于共享安装目录。有长期用途的文件应在窗口内提交到 Git 或上传持久存储。工作树通过本仓安装链接调用固定版本的登记判官。本次工作树升级同时引入了 `registration_program` 配置项。回退到 bootstrap.1 时，随该工具的版本声明一起回退此配置项。清理程序同时读取本仓的 `.chrono-harness/retention.json`，回收新产生且已无使用方的检查原件、工作树操作报告和维护清单。失败原件的诊断窗口为 24 小时。已有的未登记报告需核对具体使用方后处置。CI 任务随 GitHub 托管运行器回收。

### 为开发机的主检出启用定时清理

在长期保留的主检出中先运行 `sh .chrono-harness/ci/install.sh`。本机用户的定时器每小时运行一次 `.chrono-harness/maintain.sh`。它调用本地 `chrono-pr pr-reminders` 删除主检出中已满 30 天的 PR 提醒，再调用 `chrono-worktree maintain` 回收工作树和原件。SQLite 的空表留在主检出，工作树中的提醒库随工作树一起删除。安装器维护会回收专用目录中已满 24 小时、读者已经释放的下载。需要留存的诊断应在窗口内转存，发布恢复目录中的备份由原操作负责。任一维护失败都会使该次定时任务报告失败。机器开机、用户调度服务在运行且目录可写时，即使无人再运行开发命令，维护也会检查到期工作树。活跃租约和待保全的工作由清理程序处理。 若启用 `.chrono-harness/logging.json`，工作树维护会调用单独安装的 `chrono-diagnostics` 回收过期日志，单项失败写入本轮维护报告。

在 macOS 中将本仓的 launchd 配置安装到当前用户。以下命令从主检出根目录执行。每个路径拥有独立标签。

```sh
root=$(pwd -P)
label=org.chrono-harness.example-maintenance.$(printf %s "$root" | shasum -a 256 | cut -c1-16)
job="$HOME/Library/LaunchAgents/$label.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cp .chrono-harness/maintenance.launchd.plist "$job"
plutil -replace Label -string "$label" "$job"
plutil -replace WorkingDirectory -string "$root" "$job"
launchctl bootstrap "gui/$(id -u)" "$job"
```

删除或移动主检出前，使用同一组 `label` 和 `job` 变量，运行 `launchctl bootout "gui/$(id -u)/$label"` 和 `rm "$job"`。launchd 在下次用户登录后会加载仍已安装的配置。

在使用 systemd 用户服务的 Linux 开发机上，从主检出安装小时定时器。每个检出有独立的实例名。用户服务下次启动时会自动加载已启用的定时器，错过的维护会在恢复后补跑一次。

```sh
root=$(pwd -P)
units=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
install -d "$units"
install -m 0644 .chrono-harness/chrono-harness-example-maintenance@.service \
  .chrono-harness/chrono-harness-example-maintenance@.timer "$units/"
timer=$(systemd-escape --path --template=chrono-harness-example-maintenance@.timer "$root")
systemctl --user daemon-reload
systemctl --user enable --now "$timer"
```

删除或移动主检出前，运行 `systemctl --user disable --now "$timer"`。同一用户的其他检出可继续使用这两个单元文件。

在已登记的任务工作树中，开发者可运行 `chrono-worktree use --operation example.program` 或 `chrono-worktree use --operation example.check`。这两项 Python 操作均以 `-B` 运行并只读，在同一检出可以并行。宿主在 [.chrono-harness/cleanup.json](.chrono-harness/cleanup.json) 登记实际读取的源码与 message.txt。
