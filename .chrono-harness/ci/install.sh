#!/bin/sh
set -eu

# Hosted jobs have a fresh filesystem. Fetch mise there when it is absent.
if command -v mise >/dev/null 2>&1; then
    mise=mise
elif [ "${GITHUB_ACTIONS:-}" = true ]; then
    case "$(uname -s)/$(uname -m)" in
        Linux/x86_64) asset=linux-x64; digest=9c12c24f5eac6b6357e5265e2629166cc3005459037f5d747680a99e375ff2ab ;;
        Darwin/arm64) asset=macos-arm64; digest=87b2bd5a1b88a612ee8856df23499404b115870b5a8a8e008763c7cd51c8d412 ;;
        *) echo "Unsupported runner platform" >&2; exit 1 ;;
    esac
    stage=$(mktemp -d "$RUNNER_TEMP/example-mise.XXXXXXXX")
    trap 'rm -rf -- "$stage"' EXIT
    mise=$stage/mise
    curl -fsSL "https://github.com/jdx/mise/releases/download/v2026.11.12/mise-v2026.11.12-$asset" -o "$mise"
    (cd "$stage" && echo "$digest  mise" | shasum -a 256 -c -)
    chmod +x "$mise"
else
    echo "Install mise and run mise trust in the checkout" >&2
    exit 1
fi
if [ "${GITHUB_ACTIONS:-}" = true ]; then
    export MISE_TRUSTED_CONFIG_PATHS="$PWD"
fi
if [ -n "${CHRONO_EXAMPLE_INSTALL_ROOT:-}" ]; then
    mkdir -p "$CHRONO_EXAMPLE_INSTALL_ROOT"
    MISE_DATA_DIR=$(CDPATH= cd -- "$CHRONO_EXAMPLE_INSTALL_ROOT" && pwd -P)
    case "$MISE_DATA_DIR/" in "$(pwd -P)/"*) echo 'Choose an install directory outside the checkout' >&2; exit 2;; esac
    export MISE_DATA_DIR
fi
"$mise" install http:chrono-harness http:chrono-ci http:chrono-judge-ci http:chrono-worktree http:chrono-judge-registration http:chrono-judge-projects http:chrono-judge-filemap
mkdir -p .chrono-harness/bin
for tool in chrono-harness chrono-ci chrono-judge-ci chrono-worktree chrono-judge-registration chrono-judge-projects chrono-judge-filemap; do
    target=$("$mise" which "$tool")
    link=.chrono-harness/bin/$tool
    if [ -L "$link" ]; then
        if [ "$(readlink "$link")" = "$target" ]; then continue; fi
        ln -sfn "$target" "$link"
    else
        ln -s "$target" "$link"
    fi
done
