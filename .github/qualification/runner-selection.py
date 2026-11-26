"""Read the Linux runner selected by the adopted Copier installer after each user action."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tomllib

cmd = subprocess.check_output
def read(*args):
    return cmd(args, text=True).strip()

repo = "chrono-harness/chrono-harness-runner"
asset_name = "chrono-harness-linux-x86_64"
workspace = Path.cwd().resolve()
data = Path(os.environ["MISE_DATA_DIR"]).resolve()
baseline = read("git","rev-parse","HEAD")
assert baseline == os.environ["GITHUB_SHA"] and not data.is_relative_to(workspace)
assert platform.system() == "Linux" and platform.machine() == "x86_64"
assert not read("git","status","--porcelain")
rows = []
for selector, expected in [("v0.1.3","0.1.3"),("stable","0.1.4"),("v0.1.3","0.1.3")]:
    subprocess.run(["mise","run","harness-setup"], check=True, env={**os.environ,"CHRONO_TOOL_CHANNEL":selector})
    receipt = (workspace/".chrono-harness/state/tool-selection/versions.toml").read_bytes()
    selection = tomllib.loads(receipt.decode())
    version, linux, macos = selection["chrono-harness"]
    assert set(selection)=={"chrono-harness"} and version==expected, selection
    release = json.loads(read("gh","api",f"repos/{repo}/releases/tags/v{expected}"))
    assert not release["draft"] and not release["prerelease"] and release["tag_name"]=="v"+expected
    assets = {a["name"]:a for a in release["assets"]}
    actual = Path(read("mise","which","chrono-harness")).resolve()
    assert actual.is_relative_to(data) and not actual.is_relative_to(workspace)
    raw = actual.read_bytes()
    digest = "sha256:"+hashlib.sha256(raw).hexdigest()
    version_line = read(str(actual),"--version")
    assert (linux,macos) == (assets[asset_name]["digest"],assets["chrono-harness-macos-aarch64"]["digest"])
    assert (digest,len(raw))==(linux,assets[asset_name]["size"])
    assert version_line==f"chrono-harness {expected}"
    assert read("git","rev-parse","HEAD")==baseline
    status = read("git","status","--porcelain")
    assert not status, status
    row = dict(selector=selector,version=version_line,digest=digest,bytes=len(raw),asset=assets[asset_name]["id"],
               tag=release["tag_name"],receipt_sha256=hashlib.sha256(receipt).hexdigest(),path=str(actual),git_status=status,head=baseline)
    rows.append(row)
    print("SELECTION "+json.dumps(row,sort_keys=True),flush=True)
assert rows[0]==rows[2] and rows[0]["digest"]!=rows[1]["digest"]
