from audit import canonical, request_chain, sha, wire
from pathlib import Path
import gzip, json, subprocess, sys, zipfile

one, zipped, tool = map(Path,sys.argv[1:])
raw = one.read_bytes()
local=json.loads(gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw)
ci=json.loads(zipfile.ZipFile(zipped).read('report.json'))
tool=tool.resolve()
def invoke(cmd, body):
    p=subprocess.run([tool,cmd], input=canonical(body), capture_output=True, env={},timeout=60)
    assert p.returncode==0 and not p.stderr
    return json.loads(p.stdout)

endpoints=[]
for rep in (local,ci):
    q=request_chain(rep)[3]
    item=rep['judges'][3]
    assert sha(tool.read_bytes())==item['process']['sha256']
    data={p['argv'][-1]:json.loads(wire(p,'stdout')) for p in item['response']['outputs']['git_facts']['processes'] if 'show' in p['argv']}
    binding=dict(base=q['base']['commit'],candidate=q['candidate']['commit'],candidate_tree=q['candidate']['tree'],registry_digest=q['registries']['digest'],context_digest=q['context']['sha256'])
    ends={}
    for end in ('base','candidate'):
        oid=q[end]['commit']
        config=data[oid+':.chrono-harness/full/macos-aarch64.json']
        table=data[oid+':'+config['registries']['filemap']]
        ends[end]=dict(workflow=config['registries']['workflow'],surfaces={i['path']:i['surface'] for i in table['files'] if i['path']=='message.txt'},semantic_fields=config['semantic_fields'])
        assert ends[end]['surfaces']=={'message.txt':'product'} and ends[end]['semantic_fields']==[]
    impacts=[r['outputs']['impact'] for r in q['prior_results'] if 'impact' in r['outputs']]
    costs=[r['outputs']['costs'] for r in q['prior_results'] if 'costs' in r['outputs']]
    assert len(costs[0]['unknown'])==10
    plan=dict(**ends,delta=q['delta'],impact=q['impact'],prior_impacts=impacts,prior_costs=costs,binding=binding)
    result=invoke('plan-classification-v1',plan)
    assert result['base']==result['candidate']==[]
    w=data[q['candidate']['commit']+':'+ends['candidate']['workflow']]
    report=dict(**ends,delta=q['delta'],before={},after={},warning_code=w['mixed_change']['code'],context=result['context'])
    reply=invoke('report-v1',report)
    actual=item['response']
    assert reply==dict(status='pass',findings=[],outputs={'rule_changes':actual['outputs']['rule_changes']})
    changed={**report, 'candidate':{**report['candidate'],'surfaces':{'message.txt':'judge-policy'}}}
    assert invoke('report-v1',changed)['status']=='warn'
    endpoints.append([sha(canonical(x)) for x in [plan,result,report,reply]])
assert endpoints[0]==endpoints[1]
print(json.dumps(endpoints[0]))
