"""Read the real released FILEMAP process, then query the same checkout."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import zlib

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

stage=Path(sys.argv[1]).resolve()
root,=stage.glob("full-public-*/integration")
state=root/".chrono-harness/state"
report=json.loads((state/"report.json").read_bytes())
row,=(j for j in report["judges"] if j["id"]=="filemap")
record=row["process"]
assert row["state"]=="executed" and record["owned_work_joined"] and record["exit_code"]==0
wire=zlib.decompress(bytes.fromhex(record["stdout_zlib_hex"]))
assert record["stdout_complete"] and len(wire)==record["stdout_length"] and digest(wire)==record["stdout_sha256"]
response=json.loads(wire)
assert response==row["response"] and response["judge_id"]=="filemap"
assert response["request_id"]==row["request_id"] and record["stdin_sha256"]==row["request_digest"]
outputs=response["outputs"]
impact=outputs["impact"]
assert impact==report["impact"] and impact["delta"]==report["delta"]
assert outputs["registration_view"] is not None
request=report["request"]
binary=root/".chrono-harness/bin/chrono-judge-filemap"
assert digest(binary.read_bytes())==row["binding"]["sha256"]==record["sha256"]
runner=root/".chrono-harness/bin/chrono-harness"
env=dict(record["environment"])
assert env["PATH"]==request["observations"]["environment"]["effective"]["PATH"]

def call(command,args,value,expected=0):
    sent=json.dumps(value,separators=(",",":"),ensure_ascii=False).encode()+b"\n"
    result=subprocess.run([command,*args],cwd=root,input=sent,capture_output=True,env=env,timeout=240)
    assert result.returncode==expected,(list(map(str,[command,*args])),result.returncode,result.stderr.decode(errors="replace")[-4000:],result.stdout[:1200])
    if expected:
        return result.stderr.decode()
    return json.loads(result.stdout)

base=report["base"]
candidate=report["candidate"]
endpoint=dict(config=request["config_path"],base=base,candidate=candidate)
plain=call(binary,["endpoint-tests"],endpoint)
scheduled=call(binary,["endpoint-tests"],dict(endpoint,scheduling=True))
for result in [plain,scheduled]:
    assert result["tests"]==impact["tests"] and result["retired_tests"]==impact["retired_tests"],result
assert not {"reached","changed_paths","git_facts"}.intersection(plain)
assert scheduled["changed_paths"]==[entry["path"] for entry in impact["delta"]]
assert scheduled["git_facts"]["processes"]
assert scheduled["reached"]==sorted(impact["closure"]["reached"])
scoped=call(runner,["git-facts-v1"],dict(mode="prepared-collection",config=request["config_path"],base=base,candidate=candidate,
    context=request["context"]["path"],scope=dict(kind="collect",manifest=".chrono-harness/state/collection/manifest.json"),judge="routes"))["Ok"]["request"]
assert scoped["base"]["commit"]==base and scoped["candidate"]["commit"]==candidate and scoped["scope"]["kind"]=="collect"
assert scoped["delta"]==impact["delta"]
assert call(runner,["judge-evidence-v1"],dict(operation="validate-request",request=scoped))=={"Ok":None}
collection=call(binary,["collection-tests-v1"],dict(request=scoped,migration=None))
assert collection["tests"]==impact["tests"] and collection["retired_tests"]==impact["retired_tests"],collection
assert collection["reached"]==scheduled["reached"] and "changed_paths" not in collection,collection
assert collection["git_facts"]["processes"]
wrong=dict(scoped,scope={"kind":"unit","unit":"harness"})
assert call(binary,["collection-tests-v1"],dict(request=wrong,migration=None),2).strip()=="FILEMAP collection requires this checkout and a collection scope"
summary=call(binary,["impact-summary"],impact)
assert summary["required_tests"]==[test["node"] for test in impact["required_tests"]]
assert summary["delta"]==impact["delta"] and summary["reached"]==scheduled["reached"]
print("FILEMAP_EVIDENCE "+json.dumps(dict(candidate=candidate,base=base,binary_sha256=row["binding"]["sha256"],
      formal=dict(request_id=row["request_id"],stdout_sha256=digest(wire),delta=len(impact["delta"])),
      schedule=dict(tests=scheduled["tests"],paths=len(scheduled["changed_paths"]),git_processes=len(scheduled["git_facts"]["processes"])),
      collect=dict(verified=True,request_id=scoped["request_id"],tests=collection["tests"],git_processes=len(collection["git_facts"]["processes"]))),sort_keys=True),flush=True)
