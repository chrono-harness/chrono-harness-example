"""Compare the installed evidence queries to routes' and projects' original full-run inputs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def digest(value):
    return hashlib.sha256(value).hexdigest()

def inspect(stage):
    root, = Path(stage).resolve().glob('full-public-*/integration')
    bindir = root / '.chrono-harness/bin'
    exe = bindir / 'chrono-judge-registration'
    environment = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'])

    def call(command, query, failed=False):
        result = subprocess.run([exe, command], input=canonical(query), cwd=root,
                                env=environment, capture_output=True)
        if failed:
            assert result.returncode == 2 and not result.stdout, (command, result.returncode)
            return result.stderr.decode().strip()
        assert result.returncode == 0, (command, result.returncode, result.stderr[-600:])
        return json.loads(result.stdout)

    reports = {}
    for path in (root / '.chrono-harness/state').glob('run-*.json'):
        report = json.loads(path.read_bytes())
        template = report['request']
        assert digest(canonical(template)) == report['request_digest']
        by_id = {row['id']:row for row in report['judges']}
        route = by_id['routes']['response']['outputs']
        tests = by_id['projects']['response']['outputs']['tests']
        selected = route['global_selected']
        assert selected and selected == tests['selected'] and tests['executed']
        registration = by_id['registration']['response']['outputs']
        view = registration['registration_view']
        assert view == route['registration_view']
        effective = route['effective_inputs']
        assert effective == registration['effective_inputs']
        assert effective['endpoints']['base']['commit'] == report['base']
        assert effective['endpoints']['candidate']['commit'] == report['candidate']
        history = []
        inputs = {}
        for row in report['judges']:
            judge = row['id']
            prior = [by_id[name]['response'] for name in row['binding']['after']]
            impact = next((v['outputs']['impact'] for v in prior if 'impact' in v['outputs']), None)
            req = dict(template, judge_id=judge, request_id=row['request_id'], prior_results=prior,
                       impact=impact, observations=dict(template['observations'], judges=history))
            history = history + [{k:v for k,v in row.items() if k not in ('executable_index','request')}]
            if judge not in ('projects', 'routes'):
                continue
            assert digest(canonical(req)) == row['request_digest'] == row['process']['stdin_sha256']
            if judge == 'routes':
                command = 'route-inputs-v1'
                query = dict(request=req, view=view, selected=selected)
            else:
                command = 'project-evidence-v1'
                query = dict(request=req, view=view, evidence={'mode':'live'})
            reply = call(command, query)
            assert reply == {'request_id':row['request_id'], 'effective_inputs':effective}
            bad = {}
            for field in ('base','candidate','registry','context'):
                changed = dict(query, view=copy.deepcopy(view))
                changed['view']['binding'][field] = None
                if field == 'context' and judge == 'projects':
                    assert call(command, changed) == reply
                    continue
                diagnostic = call(command, changed, True)
                assert diagnostic == ('route' if judge == 'routes' else 'project') + ' input registration view binding mismatch', diagnostic
                bad[field] = diagnostic
            assert call(command, query) == reply
            inputs[judge] = dict(request=row['request_id'], stdin=row['request_digest'], rejected=sorted(bad))
            if judge == 'projects':
                originals = [{name:subprocess.check_output(['git','-C',root,'show',report[side]+':'+name]).decode()
                              for name in view[side]} for side in ('base','candidate')]
                projection = call('project-views-v1', dict(request=req, originals=originals, validate_inputs=True))
                assert projection['request_id'] == row['request_id'] and projection['commits'] == [report['base'], report['candidate']]
                assert projection['effective_inputs'] == {'Ok':effective} and projection['view'] == view
                defs = projection['definitions']
                docs = view['candidate']
                project_doc = docs[docs[projection['config_path']]['registries']['projects']]
                identities = sorted(kind + ':' + entry['id'] for kind in ('project','script') for entry in project_doc[kind+'s'])
                assert identities and all(defs[name] == [name] for name in identities)
                assert sorted({owner for owners in defs.values() for owner in owners}) == identities
                assert all(defs[name] for name in selected)
                inputs[judge]['owners'] = identities
        assert set(inputs) == {'routes','projects'}
        reports[path.name] = dict(candidate=report['candidate'], platform=report['git_facts']['selection']['platform'],
                                  request=inputs['routes']['request'], stdin=inputs['routes']['stdin'], judges=inputs,
                                  selected=selected, effective=effective['identity'])
    assert len(reports) == 2 and len({v['candidate'] for v in reports.values()}) == 1
    return dict(binary=digest(exe.read_bytes()), candidate=report['candidate'], reports=reports)
if __name__ == '__main__':
    print('REGISTRATION_INPUT_VIEWS ' + json.dumps(inspect(sys.argv[1]), sort_keys=True), flush=True)
