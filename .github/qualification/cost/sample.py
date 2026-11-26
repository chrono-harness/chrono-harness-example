"""Sample one previously successful README cost request with its issued programs."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess as sp,sys,zlib
from original import cost_request,h
p=Path(__file__).resolve().parent
report=Path(sys.argv[1]);out=Path(sys.argv[2]).resolve();out.mkdir(exist_ok=True)
r=json.loads(report.read_bytes());data,j=cost_request(r)
assert r['base']=='c0a3ac6966b4b4087115b450486ad63cf5a070eb' and r['candidate']=='5cd8fd8844d673724d64764661e7d806ac92039e' and r['status']=='warn'
assert h(data) in ['c12b9bdf77a291edd8ec7c4e7dc2b7f4b42132b89f6b4c0b265abb41c3469bad','5c272d57a3d5ac3cb0e57d5acdc0e65f5b154b8182a04a82d766007f7b749d6e']
req=json.loads(data);cwd=Path(req['candidate']['root']);env=req['observations']['environment']['effective']
assert sp.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=cwd,text=True).strip()==r['candidate']
def program(name,expected):
 path=Path(shutil.which(name,path=env['PATH'])).resolve(strict=True)
 assert h(path.read_bytes())==expected
 return {'path':str(path),'sha256':expected,'length':path.stat().st_size}
ids={v['id']:v['binding']['sha256'] for v in r['judges']}
programs={'runner':program('chrono-harness',req['runner']['sha256']),'reporter':program('chrono-judge-cost',ids['cost']),'filemap':program('chrono-judge-filemap',ids['filemap']),'registration':program('chrono-judge-registration',ids['registration'])}
for endpoint in ('base','candidate'):
 assert sp.check_output(['/usr/bin/git','rev-parse',req[endpoint]['commit']+'^{tree}'],cwd=cwd,text=True).strip()==req[endpoint]['tree']
# The supplied evaluator, on this separate measurement only, records the bytes
# the installed runner actually sends, then sends those same bytes to the issued reporter.
observer=out/'observe';observer.write_text('''#!/usr/bin/python3
from pathlib import Path
import hashlib,json,subprocess as sp,sys
p=Path(__file__).resolve().parent
assert sys.argv[1:]==['report-v1']
exe=Path(json.loads((p/'programs.json').read_bytes())['reporter']['path']);expected=json.loads((p/'programs.json').read_bytes())['reporter']['sha256']
assert hashlib.sha256(exe.read_bytes()).hexdigest()==expected
data=sys.stdin.buffer.read()
(p/'inner.json').write_bytes(data)
r=sp.run([exe,'report-v1'],input=data,stdout=sp.PIPE,stderr=sp.PIPE)
(p/'decision.json').write_bytes(r.stdout);(p/'reporter.stderr').write_bytes(r.stderr);(p/'reporter.exit').write_text(str(r.returncode))
sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);sys.exit(r.returncode)
''');observer.chmod(0o700)
(out/'programs.json').write_text(json.dumps(programs,indent=2)+'\n')
args=[programs['runner']['path'],'judge-pipeline','chrono-judge-cost',j['binding']['version'],programs['filemap']['path'],'cost-inputs-v1',str(observer),'report-v1',*j['binding']['argv']]
obs=sp.run(args,input=data,env=env,cwd=cwd,capture_output=True,timeout=240)
(out/'outer.json').write_bytes(obs.stdout);(out/'outer.stderr').write_bytes(obs.stderr)
expected=zlib.decompress(bytes.fromhex(j['process']['stdout_zlib_hex']))
assert obs.returncode==j['exit_code']==0 and h(expected)==j['process']['stdout_sha256'] and not obs.stderr,(obs.returncode,obs.stderr[-800:],obs.stdout[:720])
actual=json.loads(obs.stdout);wanted=json.loads(expected);assert set(actual)==set(wanted) and all(actual[k]==wanted[k] for k in wanted if k!='outputs')
assert set(actual['outputs'])==set(wanted['outputs']) and all(actual['outputs'][k]==wanted['outputs'][k] for k in wanted['outputs'] if k!='git_facts')
assert (out/'reporter.exit').read_text()=='0' and not (out/'reporter.stderr').read_bytes()
inner=(out/'inner.json').read_bytes();decision=(out/'decision.json').read_bytes();dec=json.loads(decision)
assert json.loads(inner)['binding']==r['costs']['binding'] and dec['status']=='warn' and dec['outputs']['costs']==r['costs'] and dec['findings']==j['response']['findings']
record=dict(report=h(report.read_bytes()),outer_request=h(data),outer_response=h(obs.stdout),historical_outer_response=h(expected),inner=h(inner),inner_length=len(inner),decision=h(decision),decision_length=len(decision),decision_status=dec['status'],outer_status=r['status'],exit=obs.returncode,observer=h(observer.read_bytes()),base=r['base'],candidate=r['candidate'],binding=json.loads(inner)['binding'],programs=programs)
(out/'sample.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['outer_request','inner','inner_length','decision','outer_response']}),flush=True)
