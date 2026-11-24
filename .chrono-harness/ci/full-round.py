"""Supply the worktree context and checked-out endpoint snapshots to native CI."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

host = Path.cwd()
transfer = host / ".chrono-harness/startup"
bin_dir = host / ".chrono-harness/bin"
env = dict(os.environ)
env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]


def command(argv, cwd=host, input_bytes=None):
    result = subprocess.run(argv, cwd=cwd, env=env, input=input_bytes, capture_output=True)
    if result.returncode:
        import sys
        sys.stderr.buffer.write(result.stderr)
        raise RuntimeError(f"{argv[0]} returned {result.returncode}")
    return result.stdout


def api(repo, path):
    return command(["gh", "api", f"repos/{repo}/{path}"])


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def materialize(rel):
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or path.parts[:3] != (".chrono-harness", "state", "inputs"):
        raise ValueError(f"unregistered snapshot location {rel}")
    return path


def produce():
    # The workflow token is provided only to this bootstrap action.
    repo = os.environ["GITHUB_REPOSITORY"]
    candidate = os.environ["GITHUB_SHA"]
    if os.environ["GITHUB_EVENT_NAME"] != "push" or not os.environ["GITHUB_REF"].startswith("refs/heads/integration/"):
        raise ValueError("automatic full input requires a submitted context for the integration push")
    base = command(["git", "ls-remote", "--exit-code", "origin", "refs/heads/dev"]).decode().split()[0]
    command(["git", "fetch", "--quiet", "--no-tags", "origin", base])
    name = f"full-round-{candidate}-{base}"
    artifacts = json.loads(api(repo, f"actions/artifacts?name={name}&per_page=100"))
    live = [item for item in artifacts["artifacts"] if item["name"] == name and not item["expired"]]
    if len(live) != 1 or artifacts["total_count"] > 100:
        raise ValueError(f"expected one live worktree context for {candidate} at {base}, found {len(live)}")
    artifact = live[0]
    run = json.loads(api(repo, f"actions/runs/{artifact['workflow_run']['id']}"))
    if (run["path"], run["event"], run["head_branch"], run["status"], run["conclusion"]) != (
        ".github/workflows/full-round.yml", "workflow_dispatch", "dev", "completed", "success"
    ):
        raise ValueError("context was not submitted by the registered development workflow")
    raw_zip = api(repo, f"actions/artifacts/{artifact['id']}/zip")
    if artifact["digest"] != "sha256:" + digest(raw_zip):
        raise ValueError("original artifact digest differs")
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        if archive.namelist() != ["context.json"]:
            raise ValueError("expected one original context")
        raw = archive.read("context.json")
    ctx = json.loads(raw)
    if (ctx["base"], ctx["candidate"], ctx["dev_tip"], ctx["branch_ref"]) != (
        base, candidate, base, os.environ["GITHUB_REF_NAME"]
    ):
        raise ValueError("submitted context differs from the native endpoint and branch")
    pair = materialize(ctx["retained_inputs"])
    # Secrets belong only to artifact acquisition. The installed input producer
    # records the business environment for the two actual checked-out endpoints.
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env["CHRONO_CHECK_SOURCE"] = "ci"
    # Capture against the binary search path published for the remaining jobs.
    paths = Path(os.environ["GITHUB_PATH"]).read_text().splitlines()
    env["PATH"] = os.pathsep.join(dict.fromkeys(paths[::-1] + os.environ["PATH"].split(os.pathsep)))
    # Both endpoint captures run against actual registered files and installations.
    with tempfile.TemporaryDirectory(dir=os.environ["RUNNER_TEMP"]) as temp:
        roots = {}
        for role, oid in (("base", base), ("candidate", candidate)):
            root = Path(temp) / role
            command(["git", "clone", "--quiet", "--no-local", "--no-checkout", str(host), str(root)])
            command(["git", "fetch", "--quiet", str(host), oid], root)
            command(["git", "checkout", "--quiet", "--detach", oid], root)
            endpoint_bins = root / ".chrono-harness/bin"
            endpoint_bins.mkdir(exist_ok=True)
            for tool in bin_dir.iterdir():
                (endpoint_bins / tool.name).symlink_to(tool.resolve(strict=True))
            (root / pair.parent).mkdir(exist_ok=True, parents=True)
            snapshot = str(pair) + "." + role
            command([bin_dir / "chrono-inputs", "capture", "--host-root", root, "--config",
                     ".chrono-harness/config.json", "--commit", oid, "--output", snapshot], root)
            roots[role] = root
        command([bin_dir / "chrono-inputs", "pair", "--host-root", roots["candidate"],
                 "--base-root", roots["base"], "--base-snapshot", str(pair) + ".base",
                 "--candidate-snapshot", str(pair) + ".candidate", "--output", str(pair)], roots["candidate"])
        transfer.mkdir(parents=True)
        (transfer / "context.json").write_bytes(raw)
        item = roots["candidate"] / pair
        (transfer / "pair.json").write_bytes(item.read_bytes())
        blobs = transfer / "blobs"
        blobs.mkdir()
        paired = json.loads(item.read_bytes())
        for endpoint in (paired["base"], paired["candidate"]):
            for identity in endpoint["files"].values():
                if "blob" in identity:
                    original = roots["candidate"] / materialize(identity["blob"])
                    target = blobs / identity["sha256"]
                    if not target.exists():
                        shutil.copyfile(original, target)
    binding = dict(run=os.environ["GITHUB_RUN_ID"], attempt=os.environ["GITHUB_RUN_ATTEMPT"],
                   submitted=artifact["id"], context=digest(raw), pair=digest((transfer / "pair.json").read_bytes()))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print("binding=" + json.dumps(binding, separators=(",", ":")), file=output)


def install(slot):
    binding = json.loads(os.environ["CHRONO_STARTUP_BINDING"])
    if (binding["run"], binding["attempt"]) != (os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]):
        raise ValueError("full input belongs to another native attempt")
    raw = (transfer / "context.json").read_bytes()
    pair_raw = (transfer / "pair.json").read_bytes()
    if (digest(raw), digest(pair_raw)) != (binding["context"], binding["pair"]):
        raise ValueError("full startup input differs from its detector receipt")
    ctx = json.loads(raw)
    path = host / materialize(ctx["retained_inputs"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pair_raw)
    for role, endpoint in json.loads(pair_raw).items():
        if endpoint["commit"] != ctx[role]:
            raise ValueError(f"snapshot differs from submitted {role}")
        for identity in endpoint["files"].values():
            if "blob" in identity:
                source = transfer / "blobs" / identity["sha256"]
                if digest(source.read_bytes()) != identity["sha256"] or source.stat().st_size != identity["length"]:
                    raise ValueError("retained snapshot blob differs")
                target = host / materialize(identity["blob"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    target = host / ".chrono-harness/state" / slot / "full.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("slot", choices=("produce", "collection", "example", "harness"))
    args = parser.parse_args()
    if args.slot == "produce":
        produce()
    else:
        install(args.slot)
