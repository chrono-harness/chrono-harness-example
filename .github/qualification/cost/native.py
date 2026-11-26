"""Restore the fixed observation's published programs and read-only Git endpoints."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess as sp,sys,zipfile
from original import h
root=Path.cwd().resolve();scratch=Path(os.environ['RUNNER_TEMP']);archive=scratch/'historical-cost.zip'
assert h(archive.read_bytes())=='a3adc5ed89ff5fc3d553f715028318ffcde0691e19594343ac4bdfe1d3ec7820'
with zipfile.ZipFile(archive) as z:raw=z.read('report.json')
assert h(raw)=='afb2ba9b86ed0ff6a85b083d03deeb0140bc857191c6efd9975f30719427ab0c'
old=scratch/'recorded-full.json';old.write_bytes(raw);r=json.loads(raw);q=r['request']
assert root==Path(q['candidate']['root'])
assert sp.check_output(['/usr/bin/git','rev-parse','HEAD'],text=True).strip()==q['candidate']['commit']
sp.run(['/bin/sh','.chrono-harness/ci/install.sh'],check=True)
bins=root/'.chrono-harness/bin';pathroot=Path('/private/tmp/chrono-example-206-aligned-runner-011')
pathroot.mkdir(mode=0o700)
for sub in ('installs','home','tmp'):(pathroot/sub).mkdir()
for f in bins.iterdir():
 if f.name!='git' and f.is_file():(pathroot/'installs'/f.name).symlink_to(f.resolve(strict=True))
git=Path(sp.check_output(['/usr/bin/xcrun','--find','git'],env={**os.environ,'DEVELOPER_DIR':'/Applications/Xcode_26.5.app/Contents/Developer'},text=True).strip())
assert h(git.read_bytes())=='492bd04fb367c1d51dce2be4eb6d6778829a3623dc4327318dfcdd81bc4fac2e'
shutil.copy2(git,pathroot/'installs/git');env=q['observations']['environment']['effective'];assert env['PATH'].split(':')[0]==str(pathroot/'installs')
base=Path(q['base']['root']);assert base.parent==root/'.chrono-harness/state' and base.name.startswith('base-')
base.parent.mkdir(exist_ok=True,parents=True)
sp.run(['/usr/bin/git','worktree','add','-q','--detach',str(base),q['base']['commit']],check=True)
basebin=base/'.chrono-harness/bin';basebin.mkdir(exist_ok=True)
for f in bins.iterdir():
 if f.is_file():(basebin/f.name).symlink_to(f.resolve(strict=True))
saved=q['observations']['preparation']['result'];ctx=bytes(saved['context']['raw'])
assert h(ctx)==q['context']['sha256'];target=Path(q['context']['path']);assert root/'.chrono-harness/state' in target.parents
target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(ctx)
sp.run([sys.executable,Path(__file__).with_name('sample.py'),old,scratch/'cost-sample'],check=True)
