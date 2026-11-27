"""Compare the release producer's receipt to the bytes installed and retained by its consumer."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

def sha(data):
    return hashlib.sha256(data).hexdigest()

def observe(executable, bin_directory, host, output):
    product = Path(executable).resolve(strict=True)
    host = Path(host).resolve(strict=True)
    bin_directory = Path(bin_directory).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir()
    env = {k: os.environ[k] for k in ('HOME','USER','PATH') if k in os.environ}
    env.update(PATH=str(bin_directory) + os.pathsep + env['PATH'], TMPDIR=str(output),
               CHRONO_RELEASE_LOCAL='1', CHRONO_RELEASE_RUN='host-release-110',
               CHRONO_RELEASE_ATTEMPT='1', CHRONO_RELEASE_JOB='verify_host_bootstrap_launcher_tests',
               CHRONO_RELEASE_DEPENDENCIES='{}')
    receipt_root = output / 'release'
    proc = subprocess.run([product,host,receipt_root,'--unit',env['CHRONO_RELEASE_JOB']],
                          cwd=host,env=env,capture_output=True,timeout=180)
    (output/'stdout').write_bytes(proc.stdout)
    (output/'stderr').write_bytes(proc.stderr)
    assert proc.returncode == 2, (proc.returncode,proc.stderr[-1000:])
    report = json.loads((receipt_root/'receipt.json').read_bytes())
    method, = [item for item in report['processes'] if item['phase']=='verification']
    assert method['operation']=='test.host-bootstrap-launcher-tests' and method['exit_code']==2
    installed = product.read_bytes()
    producer = report['context']['producer']
    assert len(installed) > 65536 and (producer['sha256'],producer['size'])==(sha(installed),len(installed))
    content = b'missing registered launcher fixture\n'
    originals = {'stdout': b'', 'stderr': content, 'process.json': b'{"exit_code":2}\n',
                 '.chrono-harness/state/release-test-failures/launcher.stderr': content}
    identities = {}
    for group in ('failure_evidence','registered_failure_evidence'):
        assert method[group]['status']=='retained'
        for row in method[group]['files']:
            raw = (receipt_root/row['path']).read_bytes()
            assert raw == originals[row['source']]
            assert (row['bytes'],row['sha256'])==(len(raw),sha(raw))
            identities[row['source']] = {'size':len(raw),'digest':row['sha256']}
    assert identities.keys() == originals.keys() and identities['stderr']['digest'].startswith('0d')
    for stream in ('stdout','stderr'):
        entry = method[stream]
        raw = (receipt_root/entry['path']).read_bytes()
        assert (entry['sha256'],entry['size'])==(sha(raw),len(raw))
    source = method['observation']
    assert source['engine_exit_code'] == 2 and source['exit_signal'] is None and source['failure'] is None
    assert isinstance(source['launcher_pid'], int) and source['launcher_pid'] > 0
    assert isinstance(method['pid'], int) and method['pid'] > 0 and method['pid'] != source['launcher_pid']
    assert method['finished_ns'] >= method['started_ns'] and source['output_limit_bytes'] > 0
    streams = {k: {f:method[k][f] for f in ('size','sha256')} for k in ('stdout','stderr')}
    for k in ('stdout','stderr'):
        assert 'status' not in method[k] and 'bytes' not in method[k] and method[k]['size'] <= source['output_limit_bytes']
    dependency = report['dependency_input']
    assert (receipt_root/dependency['path']).read_bytes()==b'{}'
    assert (dependency['size'],dependency['sha256'])==(2,sha(b'{}'))
    return {'pid':method['pid'],'launcher':source['launcher_pid'],'streams':streams,'engine_exit':source['engine_exit_code'],'file':producer,'originals':identities,'dependencies':dependency['sha256'],
            'operation':method['operation'],'exit':proc.returncode,'source':report['context']['source_commit']}

if __name__ == '__main__':
    print(json.dumps(observe(*sys.argv[1:]),sort_keys=True))
