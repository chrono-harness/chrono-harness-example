"""Bootstrap the qualified Xcode Git and capture native snapshots for a submitted round."""
import hashlib,json,os,shutil,subprocess as sp,tempfile
from pathlib import Path
root=Path.cwd()
sp.run(['/bin/sh','.chrono-harness/ci/install.sh'],check=True)
env=dict(os.environ)
env['DEVELOPER_DIR']='/Applications/Xcode_26.5.app/Contents/Developer'
git=Path(sp.check_output(['/usr/bin/xcrun','--find','git'],env=env,text=True).strip())
assert hashlib.sha256(git.read_bytes()).hexdigest()=='492bd04fb367c1d51dce2be4eb6d6778829a3623dc4327318dfcdd81bc4fac2e'
directory=Path(tempfile.mkdtemp(dir=os.environ['RUNNER_TEMP'],prefix='round-git-'))
shutil.copy2(git,directory/'git')
with Path(os.environ['GITHUB_PATH']).open('a') as path:path.write(str(directory)+'\n')
bins=root/'.chrono-harness/bin'
env['PATH']=str(directory)+':'+str(bins)+':'+env['PATH']
for tool in list(bins.iterdir()):
    if tool.is_file():env['PATH']+=os.pathsep+str(tool.resolve().parent)
ctx=json.loads(json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())['inputs']['context'])
pair=Path(ctx['retained_inputs'])
assert pair==Path('.chrono-harness/state/inputs/round-pair.json')
def run(*args,cwd=root):
    return sp.check_output(list(map(str,args)),cwd=cwd,env=env,text=True).strip()
assert run(git,'rev-parse','HEAD')==ctx['candidate']
with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP'],prefix='round-base-') as work:
    base=Path(work)/'base'
    run(git,'clone','-q','--no-local',root,base)
    run(git,'switch','-q','--detach',ctx['base'],cwd=base)
    basebin=base/'.chrono-harness/bin';basebin.mkdir(exist_ok=True)
    for f in bins.iterdir():(basebin/f.name).symlink_to(f.resolve(strict=True))
    for host,oid,side in [(base,ctx['base'],'base'),(root,ctx['candidate'],'candidate')]:
        (host/pair.parent).mkdir(parents=True,exist_ok=True)
        run(bins/'chrono-inputs','capture','--host-root',host,'--config','.chrono-harness/config.json','--commit',oid,'--output',str(pair.parent/('round-'+side+'.json')),cwd=host)
    run(bins/'chrono-inputs','pair','--host-root',root,'--base-root',base,'--base-snapshot',str(pair.parent/'round-base.json'),'--candidate-snapshot',str(pair.parent/'round-candidate.json'),'--output',str(pair))
