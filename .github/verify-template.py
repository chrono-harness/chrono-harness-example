"""Render the example's selected release and exercise its adopted files."""
import os
import re
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
    run_copy(source, rendered, vcs_ref=commit, data=data, defaults=True, quiet=True)
    print(f"Rendered {source}@{tag} from {commit} for {answers['repository']}")
    if os.readlink(rendered / "AGENTS.md") != os.readlink(host / "AGENTS.md") or os.readlink(host / "AGENTS.md") != "CLAUDE.md":
        raise ValueError("the example has lost its adopted agent guide")
    for path in [".github/roadmap.cjs", ".github/workflows/issue-roadmap.yml",
                 ".github/PULL_REQUEST_TEMPLATE.md", ".github/ISSUE_TEMPLATE/bug.yml",
                 ".github/ISSUE_TEMPLATE/documentation.yml", ".github/ISSUE_TEMPLATE/enhancement.yml",
                 ".github/ISSUE_TEMPLATE/question.yml", "docs/licenses/methodology-attribution.md", "docs/licenses/trureturing-Apache-2.0.txt"]:
        if (rendered / path).read_bytes() != (host / path).read_bytes():
            raise ValueError("installed template file differs: " + path)
    manifest = ".config/mise/conf.d/chrono-harness.toml"
    selected = tomllib.loads((rendered / manifest).read_text())["tools"]
    installed = tomllib.loads((host / manifest).read_text())["tools"]
    if set(selected) != set(installed):
        raise ValueError("installed tools differ from the host's Copier selection")
    for name in selected:
        if selected[name].get("bin", name) != installed[name].get("bin", name):
            raise ValueError("different installed executable for " + name)
    if "本仓是 Python 业务示例" not in (host / ".chrono-harness/USAGE.md").read_text():
        raise ValueError("the example has lost its local usage instructions")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as destination:
        verify(Path(destination))
