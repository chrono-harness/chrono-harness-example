#!/bin/sh
set -eu

# Manager and platform rows from chrono-host-bootstrap ci-install-table-v1.
ci_install_choice() {
    case $1 in
        manager-00) choice=unavailable ;;
        manager-01) choice=platform ;;
        manager-10) choice=existing ;;
        manager-11) choice=existing ;;
        platform-Darwin/arm64) choice=macos-arm64; digest=87b2bd5a1b88a612ee8856df23499404b115870b5a8a8e008763c7cd51c8d412 ;;
        platform-Linux/x86_64) choice=linux-x64; digest=9c12c24f5eac6b6357e5265e2629166cc3005459037f5d747680a99e375ff2ab ;;
        *) choice=unsupported ;;
    esac
}

# Resolve and reject storage before any install or link changes.
decision_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
MISE_DATA_DIR=$(python3 -B "$decision_dir/host_decisions.py")
MISE_DATA_DIR=${MISE_DATA_DIR%.}
export MISE_DATA_DIR

# The last two projection rows select the hosted Rust scope and occupied-link policy.
{
    IFS= read -r whitespace
    IFS= read -r schema
    IFS= read -r operation
    IFS= read -r lengths
    IFS= read -r digits
    IFS= read -r storage
    IFS= read -r rust_choices
    IFS= read -r link_choices
} < "$decision_dir/decision-values.txt"

# Hosted jobs have a fresh filesystem. Fetch mise there when it is absent.
if command -v mise >/dev/null 2>&1; then manager_available=1; else manager_available=0; fi
if [ "${GITHUB_ACTIONS:-}" = true ]; then hosted=1; else hosted=0; fi
ci_install_choice "manager-$manager_available$hosted"
case $choice in
existing)
    mise=mise
    ;;
platform)
    ci_install_choice "platform-$(uname -s)/$(uname -m)"
    case $choice in unsupported) echo 'Unsupported runner platform' >&2; exit 1;; esac
    asset=$choice
    stage=$(mktemp -d "$RUNNER_TEMP/example-mise.XXXXXXXX")
    trap 'rm -rf -- "$stage"' EXIT
    mise=$stage/mise
    curl -fsSL "https://github.com/jdx/mise/releases/download/v2026.11.12/mise-v2026.11.12-$asset" -o "$mise"
    (cd "$stage" && echo "$digest  mise" | shasum -a 256 -c -)
    chmod +x "$mise"
    ;;
unavailable)
    echo "Install mise and run mise trust in the checkout" >&2
    exit 1
    ;;
esac
if [ "${GITHUB_ACTIONS:-}" = true ]; then
    export MISE_TRUSTED_CONFIG_PATHS="$PWD"
fi
# Only the harness unit compiles the installed Verus root.
if [ "${GITHUB_ACTIONS:-}" != true ] || [ "${GITHUB_JOB:-}" = unit_harness ]; then
    "$mise" install rust
fi
"$mise" install http:chrono-distribution http:chrono-diagnostics http:chrono-pr http:chrono-harness http:chrono-ci http:chrono-judge-ci http:chrono-worktree http:chrono-judge-registration http:chrono-judge-projects http:chrono-judge-filemap http:chrono-judge-routes http:verus
mkdir -p .chrono-harness/bin
for tool in chrono-distribution chrono-diagnostics chrono-pr chrono-harness chrono-ci chrono-judge-ci chrono-worktree chrono-judge-registration chrono-judge-projects chrono-judge-filemap chrono-judge-routes verus; do
    target=$("$mise" which "$tool")
    if [ -n "${GITHUB_PATH:-}" ]; then
        dirname "$target" >> "$GITHUB_PATH"
    fi
    link=.chrono-harness/bin/$tool
    symlink=0
    same_target=0
    if [ -L "$link" ]; then
        symlink=1
        if [ "$(readlink "$link")" = "$target" ]; then same_target=1; fi
    fi
    if [ -e "$link" ]; then occupied=1; else occupied=0; fi
    link_key=$((4 * symlink + 2 * same_target + occupied + 1))
    case $(printf '%s' "$link_choices" | cut -c "$link_key") in
        k) continue ;;
        r) ln -sfn "$target" "$link" ;;
        c) ln -s "$target" "$link" ;;
        f) echo "Cannot install $tool: $link already exists and is not a symlink" >&2; exit 1 ;;
        *) echo "Invalid link decision for $tool" >&2; exit 1 ;;
    esac
done
