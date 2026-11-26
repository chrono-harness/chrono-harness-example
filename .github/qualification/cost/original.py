"""Recover the fixed cost request using only a retained successful full report."""
import copy
import hashlib
import json

def h(data):
    return hashlib.sha256(data).hexdigest()

def canonical(value):
    # This fixture uses ASCII object keys and integers in the safe JSON range.
    # Every reconstructed request must match its producer's retained byte hash.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def cost_request(report):
    original = copy.deepcopy(report['request'])
    assert original['observations']['process_encoding'] == 'chrono-retained-process/v2'
    assert h(canonical(original)) == report['judges'][0]['process']['stdin_sha256']
    index = next(i for i,row in enumerate(report['judges']) if row['id']=='cost')
    history=copy.deepcopy(report['judges'][:index])
    for item in history:
        assert item['process']['encoding']=='chrono-retained-process/v2'
        item.pop('executable_index',None)
        item.pop('request',None)
    cost=report['judges'][index]
    req=original
    req['judge_id']='cost'
    req['observations']['judges']=history
    req['prior_results']=[next(r['response'] for r in history if r['id']==pre) for pre in cost['binding']['after']]
    impact,=[r['outputs']['impact'] for r in req['prior_results'] if 'impact' in r['outputs']]
    req['impact']=impact
    req['request_id']=cost['request_id']
    data=canonical(req)
    assert h(data)==cost['process']['stdin_sha256']==cost['request_digest'],(h(data),cost['request_digest'])
    return data,cost
