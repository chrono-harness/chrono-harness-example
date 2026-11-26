"""Replay the FILEMAP selection consumed by the fixed README routes request."""
from pathlib import Path
import hashlib,json,platform,subprocess as sp,sys,zipfile,zlib

def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()

def original(row):
    process=row['process'];raw=zlib.decompress(bytes.fromhex(process['stdout_zlib_hex']))
    assert process['exit_code']==0 and process['owned_work_joined'] and process['stdout_complete']
    assert len(raw)==process['stdout_length'] and hash_bytes(raw)==process['stdout_sha256']
    assert json.loads(raw)==row['response']
    return row['response']

def main(src,exe,out):
    out.mkdir(parents=True,exist_ok=True)
    if src.suffix=='.zip':
        assert hash_bytes(src.read_bytes())=='a3adc5ed89ff5fc3d553f715028318ffcde0691e19594343ac4bdfe1d3ec7820'
        with zipfile.ZipFile(src) as archive:raw=archive.read('report.json')
    else:raw=src.read_bytes()
    assert hash_bytes(raw) in {'afb2ba9b86ed0ff6a85b083d03deeb0140bc857191c6efd9975f30719427ab0c','8e88c5df60fc4d7c67fb8282a4100a97eafbcc5073f7c9145d176a49fa307b70'}
    report=json.loads(raw)
    assert [report['base'],report['candidate']]==['c0a3ac6966b4b4087115b450486ad63cf5a070eb','5cd8fd8844d673724d64764661e7d806ac92039e']
    rows={row['id']:row for row in report['judges']}
    issuer=rows['filemap'];route=rows['routes']
    asset='8b67295c31801f79b1e1c3a0188a294d5adeda6c941c132e955694acfad56602'
    assert hash_bytes(exe.read_bytes())==issuer['process']['sha256']==asset
    history=[]
    for row in report['judges']:
        if row['id']=='routes':break
        history.append({k:v for k,v in row.items() if k not in ('request','executable_index')})
    q=report['request'].copy();q['judge_id']='routes';q['observations']={**q['observations'],'judges':history}
    q['prior_results']=[original(rows[x]) for x in route['binding']['after']]
    q['impact']=original(issuer)['outputs']['impact'];del q['request_id']
    q['request_id']=hash_bytes(encode(q));assert q['request_id']==route['request_id']
    assert hash_bytes(encode(q))==route['request_digest']==route['process']['stdin_sha256']
    actual=original(route)
    assert actual['status']=='pass' and not actual['findings']
    impact=q['impact'];assert impact==actual['outputs']['impact']
    assert q['delta']==impact['delta'] and impact['tests']==actual['outputs']['global_selected']==[]
    records={}
    def run(name,command,request,exit_code=0):
        data=encode(request)
        proc=sp.run(['chrono-judge-filemap',command],executable=exe,cwd='/',env={},input=data,capture_output=True,timeout=60)
        for field,b in [('stdin',data),('stdout',proc.stdout),('stderr',proc.stderr)]:(out/(name+'.'+field)).write_bytes(b)
        assert proc.returncode==exit_code,(name,proc.returncode,proc.stderr.decode())
        records[name]={'argv':['chrono-judge-filemap',command],'stdin':hash_bytes(data),'stdout':hash_bytes(proc.stdout),'stderr':hash_bytes(proc.stderr),'exit':proc.returncode,'lengths':[len(data),len(proc.stdout),len(proc.stderr)]}
        if exit_code:
            assert proc.stderr and proc.stdout==b''
            return
        assert not proc.stderr
        return json.loads(proc.stdout)
    summary=run('summary','impact-summary',impact)
    assert summary['schema']==impact['schema'] and summary['tests']==summary['retired_tests']==[] and summary['reached']==['file:README.md']
    assert summary['delta']==q['delta'] and actual['outputs']['global_selected']==summary['tests']
    query={'base':[],'candidate':[],'seeds':impact['seed_causes'],'reachable_only':False}
    for row in impact['edges']:
        edge={k:v for k,v in row.items() if k!='origin'}
        for side in ('base','candidate'):
            if row['origin'] in (side,'both'):query[side].append(edge)
    closure=run('closure','closure-v1',query)
    assert closure['edges']==impact['edges'] and closure['closure']==impact['closure']
    assert closure['selected_tests']==summary['tests'] and closure['reached']==summary['reached']
    newpath='message.py';node='file:'+newpath
    seed={'id':encode([newpath,'delta-path',node]).decode(),'node':node,'reason':'delta-path','reference':newpath}
    control=run('message-control','closure-v1',{**query,'seeds':[seed]})
    assert 'test:example' in control['selected_tests'] and node in control['reached']
    assert any(e['from']==node and e['kind']=='test-execution' and e['to']=='test:example' for e in query['candidate'])
    bad={'id':seed['id'],'node':'file:README.md','reference':'README.md','reason':'delta-path'}
    run('conflict-control','closure-v1',{**query,'seeds':[seed,bad]},2)
    assert b'E_SEED_ID_CONFLICT' in (out/'conflict-control.stderr').read_bytes()
    meta={'report':hash_bytes(raw),'endpoints':[report['base'],report['candidate']],'route_stdin':route['request_digest'],'route_request_id':q['request_id'],'route_stdout':route['process']['stdout_sha256'],'issuer_stdout':issuer['process']['stdout_sha256'],'filemap':asset,'architecture':platform.machine(),'cwd':'/','environment':{},'summary':summary,'controlled_tests':control['selected_tests'],'edge_counts':{k:len(query[k]) for k in ('base','candidate')},'records':records}
    (out/'replay.json').write_text(json.dumps(meta,sort_keys=True,indent=2))
    print(records['closure'],summary['tests'],control['selected_tests'],flush=True)

if __name__=='__main__':main(*(Path(x).resolve() for x in sys.argv[1:]))
