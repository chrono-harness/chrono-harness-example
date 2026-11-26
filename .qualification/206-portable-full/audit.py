"""Audit two archived reports, preserving the full wire IDs, and reconstruct finite decisions."""
import gzip
import hashlib
import json
import sys
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def without(value, *names):
    return {k: v for k, v in value.items() if k not in names}


def wire(proc, name):
    raw = zlib.decompress(bytes.fromhex(proc[name + '_zlib_hex']))
    assert proc[name + '_complete'] and len(raw) == proc[name + '_length']
    assert sha(raw) == proc[name + '_sha256']
    return raw


def request_chain(report):
    history, requests = [], []
    for row in report['judges']:
        request = dict(report['request'], judge_id=row['id'])
        request['observations'] = dict(request['observations'], judges=history.copy())
        request['prior_results'] = [next(h['response'] for h in history if h['id'] == dep)
                                    for dep in row['binding']['after']]
        impacts = [r['outputs']['impact'] for r in request['prior_results'] if 'impact' in r['outputs']]
        assert all(v == impacts[0] for v in impacts)
        request['impact'] = impacts[0] if impacts else None
        request['request_id'] = sha(canonical(without(request, 'request_id')))
        proc = row['process']
        assert request['request_id'] == row['request_id'] == row['response']['request_id']
        assert sha(canonical(request)) == row['request_digest'] == proc['stdin_sha256']
        assert proc['exit_code'] == row['exit_code'] == 0 and proc['owned_work_joined'] and proc['failure'] is None
        assert json.loads(wire(proc, 'stdout')) == row['response'] and wire(proc, 'stderr') == b''
        exe = report['executables'][row['executable_index']]
        assert proc['sha256'] == row['binding']['sha256'] == exe['sha256']
        assert proc['argv'] == [exe['path'], '--protocol', 'chrono-judge/v1']
        version = proc['judge_version_process']
        assert version['argv'] == [exe['path'], '--version'] and version['sha256'] == exe['sha256']
        assert bytes(version['stdout_bytes']).decode().strip() == exe['version']
        assert sha(bytes(version['stdout_bytes'])) == version['stdout_sha256']
        assert version['stdout_complete'] and version['stderr_complete'] and not version['stderr_bytes']
        assert version['exit_code'] == 0 and version['failure'] is None and version['owned_work_joined']
        history.append(without(row, 'request', 'executable_index'))
        requests.append(request)
    return requests


def git_pair(left, right, shallow=False):
    assert len(left) == len(right)
    for i, (a, b) in enumerate(zip(left, right)):
        for k in ('sha256','argv','cwd','environment','stdin_sha256','timeout_seconds','output_limit_bytes'):
            assert a[k] == b[k], (i,k)
        for item in (a,b):
            assert item['exit_code'] == 0 and item['failure'] is None and item['owned_work_joined']
            assert wire(item,'stderr') == b''
        x,y = wire(a,'stdout'),wire(b,'stdout')
        if shallow and i==25:
            assert a['argv'][-2:] == ['--git-path','shallow'] and x!=y
        else:
            assert x==y, i
    return len(left)


def tree(raw):
    result={}
    for item in raw.rstrip(b'\0').split(b'\0'):
        header,name=item.split(b'\t',1)
        mode,kind,oid=header.decode().split()
        assert kind=='blob'
        result[name.decode()]=(mode,oid)
    return result


def blobs(raw):
    files={}
    while raw:
        head,raw=raw.split(b'\n',1)
        oid,kind,size=head.split()
        size=int(size)
        data=raw[:size]
        assert kind==b'blob' and len(data)==size and raw[size:size+1]==b'\n'
        assert hashlib.sha1(b'blob '+str(size).encode()+b'\0'+data).hexdigest()==oid.decode()
        files[oid.decode()]=data
        raw=raw[size+1:]
    return files


def finite(report):
    q=report['request']
    obs=q['observations']
    row={j['id']:j['response'] for j in report['judges']}
    root=Path(q['candidate']['root'])
    prep=obs['preparation']
    result=prep['result']
    ctx=bytes(result['context']['raw'])
    assert str(root/result['context']['path'])==q['context']['path']
    assert sha(ctx)==sha(canonical(json.loads(ctx)))==result['context']['sha256']==q['context']['sha256']
    context=json.loads(ctx)
    assert result['base']==report['base']==context['base']==context['dev_tip']==context['fork_point']
    assert result['candidate']==report['candidate']==context['candidate']
    assert context['operation']=='validate.delta' and prep['request']['source']==result['source']
    refs={ref['path']:ref['sha256'] for ref in result['originals']}
    assert refs[result['context']['path']]==sha(ctx)
    assert refs[result['evidence']['report_path']]==result['evidence']['report_sha256']
    assert list(refs.keys()) and len(refs)==4
    reg=row['registration']['outputs']
    calls=reg['git_facts']['processes']
    streams=[wire(x,'stdout') for x in calls]
    trees=[tree(streams[8]),tree(streams[9])]
    assert set(trees[0])==set(trees[1]) and {k for k in trees[0] if trees[0][k]!=trees[1][k]}=={'message.txt'}
    delta,=q['delta']
    assert delta['kind']=='M' and delta['path']=='message.txt'
    for idx,(side,pre) in enumerate((('base','old'),('candidate','new'))):
        assert (delta[pre+'_mode'],delta[pre+'_blob'])==trees[idx]['message.txt']
        assert str(Path(q[side]['root'])/'.chrono-harness')==q['registries'][side]
        assert streams[4+idx*2].decode().strip()==q[side]['commit'] and streams[5+idx*2].decode().strip()==q[side]['tree']
        group=blobs(streams[13+4*idx])
        binding=obs['registry_bindings'][side]
        registry=reg['registration_view'][side]
        assert len(registry)==6
        for path,value in registry.items():
            if path==binding['entry_path']:
                data=streams[10+4*idx]
            elif path==binding['effective_path']:
                data=streams[11+4*idx]
            else:
                data=group[trees[idx][path][1]]
            assert json.loads(data)==value
        assert len(reg['effective_inputs']['endpoints'][side]['files'])==4
    index={}
    for item in streams[19].rstrip(b'\0').split(b'\0'):
        header,name=item.split(b'\t',1)
        mode,oid,stage=header.decode().split()
        assert stage=='0'
        index[name.decode()]=(mode,oid)
    assert index==trees[1] and len(index)==47 and not q['checkout']['tracked'] and not q['checkout']['untracked']
    assert not streams[20] and streams[18].decode().strip()==q['candidate']['commit']==q['checkout']['head']
    assert q['checkout']['index_flags']==[dict(tag=e[:1].decode(),path=e[2:].decode()) for e in streams[21].rstrip(b'\0').split(b'\0')]
    views=reg['registration_view']
    assert sha(canonical({k:views[k] for k in ('base','candidate')}))==q['registries']['digest']
    before,after=[views[end]['.chrono-harness/FILEMAP.json'] for end in ('base','candidate')]
    assert [next(v['surface'] for v in f['files'] if v['path']=='message.txt') for f in (before,after)]==['product','product']
    mixed=row['mixed']['outputs']['rule_changes']
    assert mixed['product_paths']==['message.txt'] and not mixed['rule_paths'] and not mixed['mixed']
    impact=row['filemap']['outputs']['impact']
    assert impact['tests']==['test:example'] and not impact['retired_tests']
    assert len(row['cost']['outputs']['costs']['unknown'])==10
    assert [f['code'] for f in row['cost']['findings']]==['W_COST_UNKNOWN']
    plan=row['routes']['outputs']['execution_plan']
    assert plan['identity']==sha(canonical(without(plan,'identity')))
    binding=plan['binding']
    assert binding['entry']==obs['entry'] and binding['run']==obs['run']
    assert binding['operation_state']==obs['report_path']+'.operations-'+Path(obs['report_path']).stem.removeprefix('run-')
    path=binding['entry']['resolved_paths']['paths'][0]
    assert path['actual']==path['expected'] and binding['inputs']==report['effective_inputs']
    op,=plan['operations']
    assert op['method']['operation']=='example.check' and op['method']['owner']=='script:example'
    assert op['timeout_seconds']==600 and op['output_limit_bytes']==1048576 and not op['predecessors']
    tests=row['projects']['outputs']['tests']
    execution,=tests['executed']
    rc=execution['receipt']
    assert rc['digest']==sha(canonical(without(rc,'digest')))
    assert rc['plan']==tests['plan']==plan['identity'] and tests['tests']=={'test:example':'passed'}
    assert not tests['blocked'] and execution['error'] is None
    proc=rc['process']
    tool=plan['tools'][op['method']['tool']]
    assert proc['argv']==[tool['path'],*op['method']['argv']] and proc['sha256']==tool['sha256']
    assert proc['environment']==plan['environment'] and proc['cwd']==plan['root']
    assert proc['timeout_seconds']==op['timeout_seconds'] and proc['output_limit_bytes']==op['output_limit_bytes']
    assert proc['owned_work_joined'] and proc['exit_code']==0 and proc['failure'] is None
    stdout=bytes(proc['stdout_bytes'])
    assert proc['stdout_complete'] and proc['stderr_complete'] and not proc['stderr_bytes'] and len(stdout)==4476
    assert sha(stdout)==proc['stdout_sha256'] and sha(b'')==proc['stderr_sha256']
    compiled,decoded,start=stdout.decode().splitlines()
    source=bytes.fromhex(compiled.removeprefix('compiled message.py '))
    data=bytes.fromhex(decoded.removeprefix('decoded message.txt '))
    def blob_oid(raw):
        return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert blob_oid(source)==trees[1]['message.py'][1] and blob_oid(data)==trees[1]['message.txt'][1]
    assert b'return text.strip().removeprefix("\\ufeff")' in source
    for inp,want in [(data.decode(),'hello'),('  hello  ','hello'),('\t\n',''),('  hello world\n','hello world')]:
        assert inp.strip().removeprefix('\ufeff')==want
    startup=json.loads(start.removeprefix('startup '))
    assert startup['no_site']==1 and startup['cache_present'] is False and len(startup['loader_bytes'])==24
    assert all(v[0]=='source' for v in startup['loader_bytes']) and len(startup['startup_origins'])==23
    workflow=row['workflow']['outputs']
    history=workflow['git_facts']
    branch=workflow['workflow']['branch']
    anc=[set(wire(history['processes'][i],'stdout').decode().splitlines()) for i in (22,23,24)]
    assert all(context['fork_point'] in ids for ids in anc) and not (anc[0]-anc[2])
    shallow,=history['shallow_reads']
    supplied=wire(history['processes'][25],'stdout').decode().strip()
    assert str(root/supplied)==shallow['path'] and shallow['state']=='absent' and shallow['response']=={'Ok':[]}
    observed=datetime.fromisoformat(context['observed_at'].replace('Z','+00:00'))
    started=datetime.fromisoformat(context['branch_started_at'].replace('Z','+00:00'))
    age=observed-started
    age_us=(age.days*86400+age.seconds)*1000000+age.microseconds
    policy=views['candidate']['.chrono-harness/workflow.json']['staleness']
    assert age_us==2630263 and age_us<policy['max_age_hours']*3600000000 and policy['max_behind_commits']>=0
    if result['source']=='local':
        current=branch['current_observation']
        diff=observed-datetime(1970,1,1,tzinfo=timezone.utc)
        assert current==result['evidence']['current_observation'] and current['context_digest']==sha(ctx)
        assert int(current['unix_timestamp_nanos'])==((diff.days*86400+diff.seconds)*1000000+diff.microseconds)*1000
    else:
        assert 'current_observation' not in branch
    assert context['branch_ref'].startswith('feature/') and branch['behind_commits']==0
    assert not workflow['workflow']['integration_required'] and not any(workflow['workflow']['transitions'].values())
    assert [r['status'] for r in row.values()]==['pass','pass','warn','pass','pass','pass','pass']
    assert [f for r in row.values() for f in r['findings']]==report['findings']==row['cost']['findings']
    assert report['status']=='warn' and report['publication']['exit_code']==0
    return dict(ctx=sha(ctx),stdout=sha(stdout),selection=impact['tests'],age_us=age_us,policy=policy,originals=len(refs))


def main(local_path, ci_path):
    local_raw=Path(local_path).read_bytes()
    if local_raw.startswith(b'\x1f\x8b'):
        local_raw=gzip.decompress(local_raw)
    assert sha(Path(ci_path).read_bytes())=='134acd04d668cc620198e65ab1e90900878aabde7a7af99d5c2df564d3bb5783'
    z=zipfile.ZipFile(ci_path)
    ci_raw=z.read('report.json')
    assert [sha(local_raw),sha(ci_raw)]==['9f2b6601f746cd1c5ae93917e7051f0ac95d788bac16eae68abe5712530a95b3','1b9ba0ad7c5743d29ce8657a19fae084a385a5c9c097f7a606cb02cd5bfe7c95']
    local,ci=map(json.loads,(local_raw,ci_raw))
    left,right=map(request_chain,(local,ci))
    assert len(left)==len(right)==7 and all(a['request_id']!=b['request_id'] for a,b in zip(left,right))
    for k in ('base','candidate','candidate_tree','context_digest','effective_inputs','delta','environment','findings'):
        assert local[k]==ci[k],k
    prep=ci['preparation']
    for ref in prep['result']['originals']+prep['receipts']:
        assert sha(z.read(ref['path'].split('/native-ok/')[1]))==ref['sha256']
    acq=json.loads(z.read(prep['receipts'][0]['path'].split('/native-ok/')[1]))
    assert acq['request']==prep['request']
    proc=acq['process']
    assert proc['stdin_sha256']==prep['result']['request_sha256']
    assert proc['exit_code']==0 and proc['owned_work_joined'] and proc['failure'] is None
    assert json.loads(bytes(proc['stdout_bytes']))==prep['result'] and not proc['stderr_bytes']
    assert json.loads(z.read(prep['result']['evidence']['payload']['path'].split('/native-ok/')[1]))['inputs']['context'].encode()==bytes(prep['result']['context']['raw'])
    n=git_pair(local['git_facts']['processes'],ci['git_facts']['processes'])
    assert n==23
    counts={}
    for a,b in zip(local['judges'],ci['judges']):
        key=a['id']
        assert key==b['id'] and a['binding']==b['binding']
        pa,pb=a['process'],b['process']
        assert all(pa[k]==pb[k] for k in ('cwd','environment','environment_digest','timeout_seconds','output_limit_bytes'))
        va,vb=pa['judge_version_process'],pb['judge_version_process']
        assert all(va[k]==vb[k] for k in ('sha256','stdin_sha256','stdout_bytes','stderr_bytes','cwd','environment'))
        counts[key]=git_pair(a['response']['outputs']['git_facts']['processes'],b['response']['outputs']['git_facts']['processes'],key=='workflow')
    assert sum(counts.values())==145
    assert finite(local)==finite(ci)
    print(json.dumps(dict(parent_git=n,judge_git=counts,requests=14,decision=finite(ci)),sort_keys=True))


if __name__=='__main__':
    main(*sys.argv[1:])
