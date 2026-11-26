"""Bootstrap the qualified Xcode Git and capture native snapshots for a submitted round."""
import hashlib,json,os,shutil,subprocess as sp,tempfile
from pathlib import Path
root=Path.cwd()
install_env={k:v for k,v in os.environ.items() if k!='GITHUB_PATH'}
sp.run(['/bin/sh','.chrono-harness/ci/install.sh'],env=install_env,check=True)
env=dict(os.environ)
env['DEVELOPER_DIR']='/Applications/Xcode_26.5.app/Contents/Developer'
git=Path(sp.check_output(['/usr/bin/xcrun','--find','git'],env=env,text=True).strip())
assert hashlib.sha256(git.read_bytes()).hexdigest()=='492bd04fb367c1d51dce2be4eb6d6778829a3623dc4327318dfcdd81bc4fac2e'
business=Path("/private/tmp/chrono-example-114-aligned-runner-013")
business.mkdir(mode=0o700)
directory=business/'installs';directory.mkdir()
home=business/'home';home.mkdir();tmp=business/'tmp';tmp.mkdir()
bins=root/'.chrono-harness/bin'
for f in bins.iterdir():
    if f.name!='git' and f.is_file(): (directory/f.name).symlink_to(f.resolve(strict=True))
shutil.copy2(git,directory/'git')
env.update(CHRONO_CHECK_SOURCE='ci',HOME=str(home),TMPDIR=str(tmp)+'/',PATH=str(directory)+':/usr/bin:/bin')
with Path(os.environ['GITHUB_ENV']).open('a') as output:
    for key in ('HOME','TMPDIR','PATH'):
        print(key+'='+env[key],file=output)
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
