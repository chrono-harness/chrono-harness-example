"""Exercise the installed pair query, collect two real units and check retained contributions."""
import copy, hashlib, json, os, platform, shutil, subprocess, sys
from pathlib import Path

stage=Path(sys.argv[1]).resolve()
roots=list(stage.glob('full-public-*/integration'))
if (stage/'head').is_file():
    fixed=(stage/'head').read_text().strip()
    roots=[r for r in roots if subprocess.check_output(['git','-C',r,'rev-parse','HEAD'],text=True).strip()==fixed]
root,=roots
state=root/'.chrono-harness/state'
bins=root/'.chrono-harness/bin'
runner=bins/'chrono-harness'
registration=bins/'chrono-judge-registration'
def packed(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_bytes())
def evidence(cmd,payload=None):
    return subprocess.run(cmd,cwd=root,env=env,input=None if payload is None else packed(payload)+b"\n",capture_output=True,timeout=300)
def success(cmd,payload=None):
    proc=evidence(cmd,payload)
    assert proc.returncode==0,(cmd,proc.returncode,proc.stdout[-600:],proc.stderr[-1000:])
    return proc.stdout
report=read(state/'report.json')
env={k:v for k,v in os.environ.items() if k not in ('GH_TOKEN','GITHUB_TOKEN','SSH_AUTH_SOCK')}
env.update(report['environment']['effective'])
if runner.is_symlink():
    tmp=bins/'chrono-harness-qualification-copy'
    shutil.copy2(runner.resolve(strict=True),tmp)
    assert digest(tmp.read_bytes())==report['request']['runner']['sha256']
    tmp.replace(runner)
units=report['request']['observations']['execution_units']
collection_file=root/units['report_path']
if not collection_file.is_file():
    for unit in sorted(units['units']):
        success([runner,'check','--unit',unit])
    success([runner,'check','--collect'])
full=read(root/units['report_path'])
judges={j['id']:j for j in full['judges']}
assert full['candidate']==report['candidate'] and judges['registration']['process']['sha256']==digest(registration.read_bytes())
assert judges['projects']['response']['status'] in ('pass','warn') and judges['workflow']['response']['status'] in ('warn','pass')
platform_name='macos-aarch64' if platform.system()=='Darwin' else 'linux-x86_64'
bindings=read(root/'.chrono-harness/full'/('judges-'+platform_name+'.json'))['judges']
def request_for(name):
    v=json.loads(success([runner,'judge-evidence-v1'],dict(operation='retained-judges', request=full['request'], bindings=bindings, records=full['judges'],judge=name)))
    return v['Ok']['request']
req=request_for('filemap')
assert digest(packed(req))==judges['filemap']['process']['stdin_sha256']
reg=judges['registration']['response']['outputs']['registration_view']
commits=[full['base'],full['candidate']]
originals=[{path:subprocess.check_output(['git','-C',root,'show',oid+':'+path]).decode() for path in reg[ep]} for ep,oid in zip(('base','candidate'),commits)]
def query(command,message):return json.loads(success([registration,command],message))
message=dict(operation=dict(mode='ci-collection',request=req,migration=None),originals=originals)
reply=query('impact-views-v1',message)
assert reply['request_id']==req['request_id'] and reply['commits']==commits and set(reply['outcome'])=={'ready'},reply.get('outcome',{}).get('error')
ready=reply['outcome']['ready'];assert set(ready)=={'previous','candidate','test_operations'}
bad=copy.deepcopy(message);bad['originals'][0]={}
error=query('impact-views-v1',bad)
assert error['request_id']==req['request_id'] and error['commits']==commits and isinstance(error['outcome']['error'],str) and error['outcome']['error']
assert query('impact-views-v1',message)['outcome']==reply['outcome']
selected=judges['routes']['response']['outputs']['global_selected']
inputs=dict(config=req['config_path'],selected=selected,**{ep:{path:json.loads(raw) for path,raw in doc.items()} for ep,doc in zip(('base','candidate'),originals)})
ids=query('collection-inputs-v1',inputs)
assert set(ids)=={'base','candidate'} and ids['base']!=ids['candidate']
for ep in ids:
 assert set(ids[ep])<=set(req['observations']['retained'][ep]['files'])
assert ids['candidate'] and 'python-executable' in ids['candidate'],ids
required=full['tests']['completion']['required_units']
assert required==['example','harness']
def claim(resources=(),outputs=()):return dict(resources=list(resources),outputs=list(outputs))
policy=dict(max_running=2,resources=['disk'],priority=[],claims={'write':claim(['disk'],['cache/old/']),'read':claim(['disk']),'nested':claim([],['cache/new/product']),'extra':claim()})
before=dict(scheduling=policy,operations={'test:old':['read'],'test:shared':['extra','write'],'test:unrelated':['extra']})
after=copy.deepcopy(before);del after['operations']['test:old'];after['operations']['test:nested']=['nested'];after['scheduling']['claims']['write']=claim([],['cache/new/'])
def schedule(a,b):return query('scheduling-tests-v1',[a,b])
local=['test:nested','test:old','test:shared']
assert schedule(before,after)==schedule(after,before)==local
assert schedule(before,before)==[]
all_tests=sorted(set(before['operations'])|set(after['operations']))
global_change=copy.deepcopy(after);global_change['scheduling']['max_running']=1
assert schedule(before,global_change)==all_tests
print('REGISTRATION_GRAPH '+json.dumps(dict(candidate=full['candidate'],binary=digest(registration.read_bytes()),units=required,collection=dict(outcome='ready',error=error['outcome']['error'],request=req['request_id'],commits=commits),scheduling=dict(local=local,global_tests=all_tests),input_ids=ids),sort_keys=True))
