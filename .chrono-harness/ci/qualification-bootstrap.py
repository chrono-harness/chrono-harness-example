"""Bootstrap the qualified Xcode Git and capture native snapshots for a submitted round."""
import hashlib,json,os,shutil,subprocess as sp,tempfile
from pathlib import Path
import tarfile,urllib.request
workspace=Path.cwd()
business=Path("/private/tmp/chrono-example-206-pgit");business.mkdir(mode=0o700)
root=business/"round/full/feature";root.parent.mkdir(parents=True)
# Keep the hosted workspace entry and the registered workflow paths usable
# while exposing the same physical business root as the developer run.
os.rename(workspace,root)
workspace.symlink_to(root,target_is_directory=True)
os.chdir(root)
install_env={k:v for k,v in os.environ.items() if k!="GITHUB_PATH"}
sp.run(["/bin/sh",".chrono-harness/ci/install.sh"],env=install_env,check=True)
env=dict(os.environ)
url="https://github.com/desktop/dugite-native/releases/download/v2.56.1/dugite-native-v2.56.1-238326e-macOS-arm64.tar.gz"
archive=business/"portable.tar.gz"
urllib.request.urlretrieve(url,archive)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=="a882ec6882416b57d212a22bac845ae27944f96cf73453a864f6a12c17863a79"
package=business/"portable";package.mkdir()
subprocess_args=["/usr/bin/tar","-xzf",archive,"-C",package]
sp.run(subprocess_args,check=True)
git=package/"bin/git"
assert hashlib.sha256(git.read_bytes()).hexdigest()=="af6e97b53f239d948114493c8585788dd2a1e32ddcf4191c55962b3c7e66f11f"
directory=business/"installs";directory.mkdir()
home=business/'home';home.mkdir();tmp=business/'tmp';tmp.mkdir()
bins=root/'.chrono-harness/bin'
for f in bins.iterdir():
    if f.name!='git' and f.is_file(): (directory/f.name).symlink_to(f.resolve(strict=True))
(directory/'git').symlink_to(git)
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
