#!/bin/sh
set -eu
# Keep the shared tool installation outside the task checkout.
version=v0.1.0-alpha.1
shared=${CHRONO_EXAMPLE_INSTALL_ROOT:-${RUNNER_TEMP:-${XDG_DATA_HOME:-"$HOME/.local/share"}}/chrono-harness-example/$version}
mkdir -p "$shared"
shared=$(CDPATH= cd -- "$shared" && pwd -P)
case "$shared/" in "$(pwd -P)/"*) echo 'choose a shared installation outside the checkout' >&2; exit 2;; esac
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
curl --fail --silent --show-error --location -o "$stage/install.sh" "https://github.com/chrono-harness/chrono-harness-main/releases/download/$version/install.sh"
(cd "$stage" && echo 'd88f405b9160c433402edcc12434779f7ccd978d1d9d69e558ee5fc348fdb94d  install.sh' | shasum -a 256 -c -)
sh "$stage/install.sh" --host-root "$shared" --tool chrono-harness --tool chrono-ci --tool chrono-judge-ci --tool chrono-worktree --tool chrono-judge-registration
mkdir -p .chrono-harness/bin
for tool in chrono-harness chrono-ci chrono-judge-ci chrono-worktree chrono-judge-registration; do
    link=.chrono-harness/bin/$tool
    target=$shared/.chrono-harness/bin/$tool
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then continue; fi
    ln -s "$target" "$link"
done
