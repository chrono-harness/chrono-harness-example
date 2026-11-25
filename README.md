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

### 为主检出启用事件触发的维护

在主检出运行 `sh .chrono-harness/ci/install.sh`，并创建用户私有的 `.chrono-harness/state/`。工作树和 runner 在业务完成后向同一 Unix 数据报套接字发送事件。系统激活一个持有协调者排他租约的维护者，按登记的窗口处置工作树、原件和已启用的日志。宿主还登记了两个独立消费者，`chrono-pr pr-reminders` 清理已满 30 天的本地提醒，`chrono-distribution maintain` 回收已满 24 小时且读者已释放的安装下载。某项失败后，其余操作继续，维护报告保存各项真实结果。

到期只改变清理资格。之后首个业务事件或显式运行 `.chrono-harness/bin/chrono-worktree maintain` 时会再次检查；机器空闲时没有固定回收时限。请在窗口内将有价值的产物移入 Git 或其他持久存储。服务未安装时业务 stderr 会报告 `wake-failed`；`requested` 表示数据报已发出，原始维护报告记录实际处置。

在 macOS 的用户会话中，从主检出运行以下命令。替换已安装的旧 job 时，先卸载同一检出的旧版本。安装路径需满足 Unix 套接字长度限制。

```sh
root=$(pwd -P)
label=org.chrono-harness.example-maintenance.$(printf %s "$root" | shasum -a 256 | cut -c1-16)
job="$HOME/Library/LaunchAgents/$label.plist"
install -d -m 0700 "$root/.chrono-harness/state"
mkdir -p "$HOME/Library/LaunchAgents"
if launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$label"
fi
cp .chrono-harness/maintenance.launchd.plist "$job"
plutil -replace Label -string "$label" "$job"
plutil -replace WorkingDirectory -string "$root" "$job"
plutil -replace ProgramArguments.0 -string "$root/.chrono-harness/bin/chrono-worktree" "$job"
plutil -replace Sockets.Maintenance.SockPathName -string "$root/.chrono-harness/state/maintenance.sock" "$job"
launchctl bootstrap "gui/$(id -u)" "$job"
```

移动或删除主检出前，执行 `launchctl bootout "gui/$(id -u)/$label"` 并移除该 job 文件。

Linux 使用 systemd 用户 socket。以下命令从主检出运行，先停用该检出已安装的小时定时器，再安装 socket 和 service。

```sh
root=$(pwd -P)
units=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
install -d -m 0700 "$root/.chrono-harness/state"
install -d "$units"
instance=$(systemd-escape --path "$root")
prefix=chrono-harness-example-maintenance
if [ -f "$units/$prefix@.timer" ]; then
  systemctl --user disable --now "$prefix@$instance.timer"
fi
install -m 0644 ".chrono-harness/$prefix@.service" ".chrono-harness/$prefix@.socket" "$units/"
systemctl --user daemon-reload
systemctl --user enable --now "$prefix@$instance.socket"
```

移动或删除主检出前，执行 `systemctl --user disable --now "$prefix@$instance.socket"`，等待该实例正在执行的维护结束。其他检出的实例继续独立运行。

在已登记的任务工作树中，开发者可运行 `chrono-worktree use --operation example.program` 或 `chrono-worktree use --operation example.check`。这两项 Python 操作均以 `-B` 运行并只读，在同一检出可以并行。宿主在 [.chrono-harness/cleanup.json](.chrono-harness/cleanup.json) 登记实际读取的源码与 message.txt。
