from pathlib import Path
import hashlib,json,sys,zlib
state,=Path(sys.argv[1]).glob('full-public-*/integration/.chrono-harness/state')
records={}
for f in state.glob('run-*.json'):
    r=json.loads(f.read_bytes());judges={j['id']:j for j in r['judges']}
    j=judges['cost'];proc=j['process']
    raw=zlib.decompress(bytes.fromhex(proc['stdout_zlib_hex']))
    assert proc['stdout_complete'] and proc['exit_code']==0 and proc['owned_work_joined']
    assert len(raw)==proc['stdout_length'] and hashlib.sha256(raw).hexdigest()==proc['stdout_sha256']
    response=json.loads(raw);assert response==j['response'] and response['status']=='warn' and any(i['code']=='W_COST_UNKNOWN' for i in response['findings'])
    c=response['outputs']['costs'];items=c['unknown'];assert items and c['binding']==judges['mixed']['response']['outputs']['rule_changes']['binding'] and c['measured'] is None
    expected=[]
    keys=['cpu_ms','wall_ms','peak_rss_bytes','io_bytes']
    for node in sorted(c['declared_before']):
        for side,key in [('base','declared_before'),('candidate','declared_after')]:
            entry=c[key][node]
            if entry is None:continue
            members=entry['costs']
            if not members:expected.append(dict(endpoint=side,node=node,reference=None,coordinates=keys,reason='no declared member cost references'))
            for m in members:
                missing=[k for k in keys if m['value'].get(k) is None]
                if missing:expected.append(dict(endpoint=side,node=node,member=m['member'],reference=m['reference'],source=m['source'],reason=m['value'].get('basis'),coordinates=missing))
    assert items==expected
    out=judges['workflow']['response']['outputs']['workflow'];cert=hashlib.sha256((state/'integration.json').read_bytes()).hexdigest();assert out['integration']['sha256']==cert
    mode=out['mode'];assert mode not in records
    records[mode]=dict(candidate=r['candidate'],report=hashlib.sha256(f.read_bytes()).hexdigest(),cost_stdout=proc['stdout_sha256'],entries=len(items),certificate=cert)
assert set(records)=={'integration_run','delivery'}
print('COST_PROTOCOL '+json.dumps(records,sort_keys=True))
