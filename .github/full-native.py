"""Exercise the example's fixed full policy using only independently installed releases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

seed = Path(sys.argv[1]).resolve()
stage = Path(sys.argv[2]).resolve()
root = Path(tempfile.mkdtemp(dir=stage, prefix="full-public-"))
origin = root / "origin.git"
base = root / "dev"
candidate = root / "integration"
binaries = seed / ".chrono-harness/bin"
baseline = "40df221c47d130fa9a3d41bfd27e4f90eb216067"
env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK")}
env.update(PATH=str(binaries) + os.pathsep + env["PATH"], CHRONO_AGENT_ID="full-release-consumer", CHRONO_CHECK_SOURCE="local")
git = "/usr/bin/git"

def run(program, cwd, *, summary=False):
    result = subprocess.run(program, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    if result.returncode:
        print(result.stderr[-3000:], result.stdout[-3700:], file=sys.stderr)
        raise RuntimeError(f"{program[0]} returned {result.returncode}")
    if summary:
        print(result.stdout[-1500:], flush=True)
    return result.stdout

def installed(repo):
    directory = repo / ".chrono-harness/bin"
    directory.mkdir(exist_ok=True)
    for binary in binaries.iterdir():
        target = binary.resolve(strict=True)
        assert seed not in target.parents and candidate not in target.parents
        (directory / binary.name).symlink_to(target)
    (repo / ".chrono-harness/state/inputs").mkdir(parents=True, exist_ok=True)

def head(repo):
    return run([git, "rev-parse", "HEAD"], repo).strip()

tip = head(seed)
print(f"base {baseline} candidate {tip} temporary host {root}", flush=True)
run([git, "clone", "--bare", "--no-local", seed, origin], root)
run([git, "update-ref", "refs/heads/dev", baseline], origin)
run([git, "clone", "-b", "dev", origin, base], root)
installed(base)
birth = json.loads(run([binaries / "chrono-worktree", "start", "--host-root", base, "--config", ".chrono-harness/worktree.json", "--path", candidate, "--kind", "integration", "--name", "public-full"], base))
assert birth["status"] == "created"
run([git, "fetch", seed, tip], candidate)
run([git, "merge", "--ff-only", tip], candidate)
installed(candidate)
assert head(base) == baseline and head(candidate) == tip
purpose = ".chrono-harness/state/inputs/" + str(time.time_ns())
for repo, endpoint in ((base, "base"), (candidate, "candidate")):
    run([binaries / "chrono-inputs", "capture", "--host-root", repo, "--config", ".chrono-harness/config.json", "--commit", head(repo), "--output", purpose + "-" + endpoint + ".json"], repo)
run([binaries / "chrono-inputs", "pair", "--host-root", candidate, "--base-root", base, "--base-snapshot", purpose + "-base.json", "--candidate-snapshot", purpose + "-candidate.json", "--output", purpose + "-pair.json"], candidate)
state = candidate / ".chrono-harness/state"
origin_file = state / "origin.json"
current = json.loads(origin_file.read_bytes())
current["retained_inputs"] = purpose + "-pair.json"
origin_file.write_text(json.dumps(current) + "\n")
for mode in ("integration_run", "delivery"):
    try:
        run([".chrono-harness/bin/chrono-harness", "check"], candidate, summary=True)
    finally:
        report_path = state / "report.json"
        if report_path.is_file():
            report = json.loads(report_path.read_bytes())
            print("actual findings", [(f["code"], f["message"][:220]) for f in report["findings"]], flush=True)
    verdict = report["judges"][-1]["response"]["outputs"]["workflow"]
    assert report["base"] == baseline and report["candidate"] == tip and verdict["mode"] == mode
    assert len(report["judges"]) == 7 and all(j["state"] == "executed" and j["exit_code"] == 0 for j in report["judges"])
    assert {x["operation"] for x in report["tests"]["executed"]} == {"example.check", "installer.check-location", "ci.verify"}
    cert_sha = hashlib.sha256((state / "integration.json").read_bytes()).hexdigest()
    assert verdict["integration"]["sha256"] == cert_sha
    print(json.dumps({"mode": mode, "base": baseline, "candidate": tip, "tree": report["candidate_tree"], "report": hashlib.sha256((candidate / report["report_path"]).read_bytes()).hexdigest(), "certificate": cert_sha, "executed": len(report["judges"]), "completeness": verdict["input_completeness_proven"]}))
    if mode == "integration_run":
        current.update(run_kind="delivery", integration_evidence=cert_sha)
        origin_file.write_text(json.dumps(current) + "\n")
