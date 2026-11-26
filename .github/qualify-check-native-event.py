import contextlib
import plistlib
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request

root = Path(tempfile.mkdtemp(prefix="chrono75-", dir="/tmp")).resolve() / "host"
base = root.parent
checkout = Path(os.environ["GITHUB_WORKSPACE"])
env = dict(os.environ)
host_commit = "d2b64f871ed82740460cc6af66c950a9c9313be0"
keep = 8

def run(*args, cwd=None, data=None, ok=True):
    done = subprocess.run(args, input=data, cwd=cwd or root, env=env, capture_output=True)
    if ok and done.returncode:
        raise RuntimeError((args, done.returncode, done.stdout[-1000:], done.stderr[-4000:]))
    return done

def text(path):
    return json.loads(path.read_bytes())

def put(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def json_row(data):
    return json.loads(data.decode())

def lines(path):
    rows = []
    for s in path.read_text().splitlines():
        try:
            rows.append(json.loads(s))
        except ValueError:
            pass
    return rows

run("git", "clone", "--quiet", "--no-local", str(checkout), str(root), cwd=base)
run("git", "checkout", "-q", "-B", "dev", host_commit)
run("git", "init", "-q", "--bare", "-b", "dev", str(base/"origin.git"))
run("git", "remote", "set-url", "origin", str(base/"origin.git"))
cfg = root/".chrono-harness/worktree.json"
policy = text(cfg)
policy["maintenance_operations"] = {"opt-in-checks":{"program":".chrono-harness/bin/mise","args":["run","harness-maintain-checks"]}}
put(cfg,policy)
cf = root/".chrono-harness/retention.json"
retention = text(cf)
retention["keep_seconds"] = 180
retention["terminal_limits"] = {"check-original":{"keep_seconds":keep,"max_count":128,"max_bytes":67108864,"metadata_keep_seconds":180}}
put(cf,retention)
run("git","-c","user.name=qualification","-c","user.email=checkout@localhost","commit","-qam","Select native scratch and eight-second check-original retention")
run("git","push","-qu","origin","dev")
bins = root/".chrono-harness/bin"
# Use the installer pin from the example checkout and preserve mise for the service.
mise=base/"mise"
with urllib.request.urlopen("https://github.com/jdx/mise/releases/download/v2026.11.12/mise-v2026.11.12-macos-arm64") as inp, mise.open("xb") as out:
    shutil.copyfileobj(inp,out)
assert sha(mise)=="87b2bd5a1b88a612ee8856df23499404b115870b5a8a8e008763c7cd51c8d412"
mise.chmod(0o755)
env["PATH"]=str(base)+":"+env["PATH"]
env["MISE_TRUSTED_CONFIG_PATHS"]=str(root)
run("sh",".chrono-harness/ci/install.sh")
pinned=tomllib.loads((root/".config/mise/conf.d/chrono-harness.toml").read_text())["tools"]
for name in ["chrono-worktree","chrono-harness"]:
    assert pinned["http:"+name]["version"]=="0.1.0"
    assert "sha256:"+sha(bins/name)==pinned["http:"+name]["platforms"]["macos-arm64"]["checksum"]
run(sys.executable,"-m","venv",str(base/"copier-env"))
run(str(base/"copier-env/bin/pip"),"--disable-pip-version-check","install","copier==9.19.1")
render=base/"render"
data=dict(features=[],local_check_retention=True,native_check_keep_seconds=keep,generate_check=False,github_templates=False,manage_roadmap=False,tool_versions={"chrono-harness":"v0.1.0","chrono-host-bootstrap":"v0.1.0"})
answers=base/"answers.json";put(answers,data)
run(str(base/"copier-env/bin/copier"),"copy","--defaults","--vcs-ref","v0.1.40","--data-file",str(answers),"gh:chrono-harness/chrono-harness-copier",str(render))
for folder,files in {".config/mise/conf.d":["chrono-harness.toml","selected-chrono-harness.toml"],".chrono-harness":["setup-check-retention.sh","install-tools.sh","template-answers.yml","maintain-checks.json"]}.items():
    for f in files:
        shutil.copyfile(render/folder/f,root/folder/f)
assert (root/".config/mise/conf.d/chrono-harness.toml").read_bytes()==(render/".config/mise/conf.d/chrono-harness.toml").read_bytes()
run("git","add","-f",".config/mise/conf.d/chrono-harness.toml",".config/mise/conf.d/selected-chrono-harness.toml",".chrono-harness/setup-check-retention.sh",".chrono-harness/install-tools.sh",".chrono-harness/template-answers.yml",".chrono-harness/maintain-checks.json")
run("git","-c","user.name=qualification","-c","user.email=checkout@localhost","commit","-qm","Adopt the stable Copier optional maintenance task")
run("git","push","-qu","origin","dev")
run(str(mise),"trust","--yes")
run(str(mise),"run","harness-setup")
bootstrap=Path(run(str(mise),"which","chrono-host-bootstrap").stdout.decode().strip())
assert sha(bootstrap)=="46bf5253b77c2103e481db7912cce0bbe6f74291b64994f9486d08b7edc51deb"
assert sha(Path(run(str(mise),"which","chrono-harness").stdout.decode().strip()))==sha(bins/"chrono-harness")
(bins/"mise").symlink_to(mise)
env["PATH"]=str(bins)+":"+env["PATH"]
state=root/".chrono-harness/state"
state.mkdir(exist_ok=True)
service_out=base/"service.stdout"
service_err=base/"service.stderr"
service_out.touch(); service_err.touch()
fixture=state/"qualification-check.json"
sample=run(sys.executable,"-B","check.py")
document=json.dumps({"argv":["python3","-B","check.py"],"stdout":sample.stdout.decode(),"stderr":sample.stderr.decode(),"exit":sample.returncode})+"\n"
def retained(request):
    done=run(str(bins/"chrono-harness"),"retained-artifacts-v1",data=json.dumps(request).encode()+b"\n")
    reply=json_row(done.stdout); assert "Ok" in reply,reply
    return done
retained({"operation":"publish-text","producer":"check-original","path":str(fixture.relative_to(root)),"text":document,"outcome":{"state":"completed","exit":0}})
assert fixture.read_text()==document
copied=base/"preserved-check.json";shutil.copyfile(fixture,copied)
native=run(str(bootstrap),"native-scratch","run",sys.executable,"-c",'import pathlib,os,sys; p=pathlib.Path(os.environ["CHRONO_NATIVE_SCRATCH"]); (p/"partial.log").write_text("qualification compiler stopped"); print(p); sys.exit(7)',ok=False)
assert native.returncode==7,native.stderr
scratch=Path(native.stdout.decode().strip());assert scratch.is_relative_to(root/"target/native-checks") and (scratch/"partial.log").is_file()
copied_log=base/"preserved-scratch.log";shutil.copyfile(scratch/"partial.log",copied_log)
digests={"check":sha(fixture),"native":sha(scratch/"partial.log")}
with contextlib.ExitStack() as close:
    conf=plistlib.loads((root/".chrono-harness/maintenance.launchd.plist").read_bytes())
    label="org.chrono-harness.copier75."+str(os.getpid());domain="gui/"+str(os.getuid());sock=state/"maintenance.sock"
    conf.update(Label=label,WorkingDirectory=str(root),StandardOutPath=str(service_out),StandardErrorPath=str(service_err))
    conf["ProgramArguments"][0]=str(bins/"chrono-worktree");conf["EnvironmentVariables"].update(PATH=env["PATH"],MISE_TRUSTED_CONFIG_PATHS=str(root))
    conf["Sockets"]["Maintenance"]["SockPathName"]=str(sock);job=base/"service.plist";job.write_bytes(plistlib.dumps(conf))
    run("launchctl","bootstrap",domain,str(job));close.callback(run,"launchctl","bootout",domain+"/"+label,ok=False)
    assert sock.is_socket()
    fd=os.open(service_out,os.O_RDONLY);close.callback(os.close,fd)
    queue=select.kqueue();close.callback(queue.close)
    queue.control([select.kevent(fd,filter=select.KQ_FILTER_VNODE,flags=select.KQ_EV_ADD|select.KQ_EV_CLEAR,fflags=select.KQ_NOTE_WRITE)],0,0)
    time.sleep(keep+2)
    assert fixture.is_file() and scratch.is_dir() and not lines(service_out)
    fired=retained({"operation":"retain-original-text","directory":".chrono-harness/state/","prefix":"handoff","text":"wake scope 75"})
    notices=[json.loads(v.removeprefix("W_MAINTENANCE_ACTIVATION: ")) for v in fired.stderr.decode().splitlines() if v.startswith("W_MAINTENANCE_ACTIVATION: ")]
    assert any(n["accepted"] and n["status"]=="requested" for n in notices),notices
    deadline=time.monotonic()+90
    while not any(row.get("status")=="maintenance-queue-empty" and row.get("owned_work_joined") is True for row in lines(service_out)):
        remaining=deadline-time.monotonic()
        if remaining<=0 or not queue.control(None,1,remaining):
            raise RuntimeError((service_out.read_text(),service_err.read_text()[-5000:]))
    refs=[row for row in lines(service_err) if row.get("schema")=="chrono-maintenance-round-reference/v1"]
    assert refs,service_err.read_text()[-5000:]
    ref=refs[-1];assert ref["trigger"]=="event" and ref["status"]=="maintained",ref
    round_doc=text(root/ref["report_path"]);assert round_doc["owned_work_joined"] and round_doc["maintenance_trigger"]=="event"
    op=round_doc["maintenance_operations"]["opt-in-checks"]
    assert op["exit_code"]==0,(op,service_err.read_text()[-1000:])
    assert not scratch.exists() and not fixture.exists(),(scratch.exists(),fixture.exists(),round_doc.get("output_retention"))
    assert sha(copied)==digests["check"] and sha(copied_log)==digests["native"]
    result={"host":host_commit,"policy_commit":run("git","rev-parse","HEAD").stdout.decode().strip(),"platform":sys.platform,"keep_seconds":keep,"input_check":document,"transfer_digests":digests,"protected_until_event":True,"expired_check_gone":True,"expired_native_scratch_gone":True,"service_trigger":ref["trigger"],"maintenance_original_sha256":sha(root/ref["report_path"]),"maintenance_task_exit":op["exit_code"],"copier":"v0.1.40","template_task":sha(render/".config/mise/conf.d/chrono-harness.toml")}
    print(json.dumps(result),flush=True)
    archive=Path(os.environ["RUNNER_TEMP"])/"copier-75-receipts";archive.mkdir()
    put(archive/"observations.json",result);shutil.copyfile(root/ref["report_path"],archive/"maintenance.json")
    for f in (service_out,service_err,copied,copied_log):shutil.copyfile(f,archive/f.name)

