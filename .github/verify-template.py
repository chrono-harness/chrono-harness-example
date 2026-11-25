"""Render the example's selected release and exercise its adopted files."""
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

import yaml
from copier import run_copy


def verify(rendered):
    host = Path.cwd()
    answers = yaml.safe_load((host / ".chrono-harness/template-answers.yml").read_text())
    source = answers["_src_path"]
    tag = answers["_commit"]
    if source != "gh:chrono-harness/chrono-harness-copier" or not re.fullmatch(r"v\d+\.\d+\.\d+(?:-alpha\.\d+)?", tag):
        raise ValueError("expected a tagged chrono-harness template release")
    remote = "https://github.com/" + source.removeprefix("gh:") + ".git"
    ref = "refs/tags/" + tag
    commit, found = subprocess.check_output(["git", "ls-remote", "--exit-code", remote, ref], text=True).split()
    if found != ref or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("cannot resolve the selected template tag")
    data = {key: value for key, value in answers.items() if not key.startswith("_")}
    manifest = ".config/mise/conf.d/chrono-harness.toml"
    host_config = tomllib.loads((host / manifest).read_text())
    release_tool = host_config["tools"]["http:chrono-host-release"]
    data["host_release_artifact"] = {
        "version": release_tool["version"],
        "linux_sha256": release_tool["platforms"]["linux-x64"]["checksum"].removeprefix("sha256:"),
        "macos_sha256": release_tool["platforms"]["macos-arm64"]["checksum"].removeprefix("sha256:"),
    }
    run_copy(source, rendered, vcs_ref=commit, data=data, defaults=True, quiet=True)
    print(f"Rendered {source}@{tag} from {commit} for {answers['repository']}")
    if os.readlink(rendered / "AGENTS.md") != os.readlink(host / "AGENTS.md") or os.readlink(host / "AGENTS.md") != "CLAUDE.md":
        raise ValueError("the example has lost its adopted agent guide")
    for path in [".chrono-harness/install-tools.sh", ".config/mise/conf.d/.gitignore",
                 ".config/mise/conf.d/selected-chrono-harness.toml",
                 ".github/roadmap.cjs", ".github/workflows/issue-roadmap.yml",
                 ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug.yml",
                 ".github/ISSUE_TEMPLATE/documentation.yml", ".github/ISSUE_TEMPLATE/enhancement.yml",
                 ".github/ISSUE_TEMPLATE/question.yml", "docs/licenses/methodology-attribution.md", "docs/licenses/trureturing-Apache-2.0.txt"]:
        if (rendered / path).read_bytes() != (host / path).read_bytes():
            raise ValueError("installed template file differs: " + path)
    rendered_config = tomllib.loads((rendered / manifest).read_text())
    if answers.get("local_check_retention") is not False:
        raise ValueError("the example uses its registered worktree maintenance")
    if answers.get("native_check_keep_seconds") != 0:
        raise ValueError("the Python example does not produce native compilation directories")
    for root in (host, rendered):
        if (root / ".chrono-harness/maintain-checks.json").exists():
            raise ValueError("unexpected standalone retention request in the example")
        if "harness-maintain-checks" in tomllib.loads((root / manifest).read_text())["tasks"]:
            raise ValueError("unexpected second maintenance task in the example")
    if host_config["tasks"]["harness-setup"]["run"] != rendered_config["tasks"]["harness-setup"]["run"]:
        raise ValueError("host setup must use the rendered tool installer")
    if host_config["settings"]["task"]["run_auto_install"] is not False:
        raise ValueError("setup must resolve tools before mise installs them")
    selected = rendered_config["tools"]
    installed = host_config["tools"]
    if set(selected) != set(installed):
        raise ValueError("installed tools differ from the host's Copier selection")
    for name in selected:
        if selected[name].get("bin", name) != installed[name].get("bin", name):
            raise ValueError("different installed executable for " + name)
    if "本仓是 Python 业务示例" not in (host / ".chrono-harness/USAGE.md").read_text():
        raise ValueError("the example has lost its local usage instructions")


def install_diagnostics(rendered):
    config_dir = rendered / ".config/mise/conf.d"
    shutil.copyfile(".config/mise/conf.d/chrono-harness.toml", config_dir / "chrono-harness.toml")
    tools = tomllib.loads((config_dir / "chrono-harness.toml").read_text())["tools"]
    tool = "http:chrono-diagnostics"
    version = tools[tool]["version"]
    disabled = ",".join(name for name in tools if name != tool)
    env = {**os.environ, "MISE_DISABLE_TOOLS": disabled, "MISE_TRUSTED_CONFIG_PATHS": str(rendered)}
    env.pop("CHRONO_TOOL_CHANNEL", None)
    command = ["sh", ".chrono-harness/install-tools.sh"]
    receipt = rendered / ".chrono-harness/state/tool-selection/versions.toml"
    subprocess.run(command, cwd=rendered, env={**env, "CHRONO_TOOL_CHANNEL": "v" + version}, check=True)
    observed = tomllib.loads(receipt.read_text())
    if set(observed) != {"chrono-diagnostics"} or observed["chrono-diagnostics"][0] != version:
        raise ValueError("the exact override did not resolve the selected diagnostics release")
    trace = subprocess.run(
        ["mise", "exec", "--", "chrono-diagnostics", "trace-events-v1", "--sink-only", "example"],
        input='"finish"\n"ok"\n', capture_output=True, text=True, cwd=rendered, env=env, check=True,
    )
    if trace.stdout.splitlines() != ['"ready"', '"flush"', '{"finished":[]}']:
        raise ValueError("the installed diagnostics did not deliver its terminal reply")
    subprocess.run(command, cwd=rendered, env=env, check=True)
    selected = tomllib.loads(receipt.read_text())
    if set(selected) != {"chrono-diagnostics"}:
        raise ValueError("the repository's tool choice was not preserved")
    stable = selected["chrono-diagnostics"][0]
    if not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+", stable):
        raise ValueError("expected a stable diagnostics release from the repository policy")
    checked = subprocess.run(
        ["mise", "exec", "--", "chrono-diagnostics", "--version"],
        capture_output=True, text=True, env=env, cwd=rendered, check=True,
    )
    if checked.stdout.strip() != "chrono-diagnostics " + stable:
        raise ValueError("the installed diagnostics did not report the resolved stable version")
    print(f"Exercised exact diagnostics v{version}, then installed repository-selected stable v{stable}")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as destination:
        verify(Path(destination))
        install_diagnostics(Path(destination))
