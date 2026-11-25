"""Exercise the released installer against the Python example on its real dev branch."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import tempfile
import tomllib

from copier import run_copy


root = Path.cwd()
source = 'gh:chrono-harness/chrono-harness-copier'
component = 'chrono-pr'
repository = 'chrono-harness/chrono-harness-pr'
platform_name, asset_name = {
    ('Darwin', 'arm64'): ('macos-arm64', 'chrono-pr-macos-aarch64'),
    ('Linux', 'x86_64'): ('linux-x64', 'chrono-pr-linux-x86_64'),
}[(platform.system(), platform.machine())]


def git(*args, cwd=root):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def release(tag):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/releases/tags/{tag}']))


def newest_preview():
    pages = json.loads(subprocess.check_output([
        'gh', 'api', '--paginate', '--slurp', f'repos/{repository}/releases?per_page=100',
    ]))
    candidates = [row for page in pages for row in page if row['prerelease'] and not row['draft']]
    return max(candidates, key=lambda row: (row['published_at'], row['id']))['tag_name']


def verified_install(host, env, tool):
    tag = 'v' + tool['version']
    published = release(tag)
    assert published['tag_name'] == tag and not published['draft']
    asset = next(a for a in published['assets'] if a['name'] == asset_name)
    pin = tool['platforms'][platform_name]
    assert pin['url'] == asset['browser_download_url'] and pin['checksum'] == asset['digest']
    binary = Path(subprocess.check_output(['mise', 'which', component], cwd=host, env=env, text=True).strip())
    assert host.resolve() not in binary.resolve().parents
    digest = 'sha256:' + hashlib.sha256(binary.read_bytes()).hexdigest()
    assert digest == asset['digest']
    result = json.loads(subprocess.check_output([binary, 'pr-reminders'], cwd=host, env=env))
    assert result['schema'] == 'chrono-pr-reminders/v1'
    print(f"{platform_name} {tag} {digest} {binary}", flush=True)
    return tag, published['prerelease'], binary


with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as stage_name:
    stage = Path(stage_name)
    host = stage/'example'
    upstream_dev = os.environ['EXAMPLE_DEV_SHA']
    git('clone', '--quiet', '--no-local', str(root), str(host))
    prior_adoption = '3aed83c1a46492af010de5ef1f1e20d87e3af39d'
    git('merge-base', '--is-ancestor', prior_adoption, upstream_dev, cwd=host)
    git('switch', '-C', 'dev', prior_adoption, cwd=host)
    env = {**os.environ, 'MISE_DATA_DIR':str(stage/'tools'), 'MISE_TRUSTED_CONFIG_PATHS':str(host)}
    # This inner Git checkout represents a developer running the installer locally.
    # The outer Actions run belongs to the profile branch that owns this acceptance.
    for key in list(env):
        if key.startswith('GITHUB_') or key == 'CHRONO_INSTALL_BRANCH':
            del env[key]
    if 'GH_TOKEN' in env:
        env['GITHUB_TOKEN'] = env['GH_TOKEN']
    manifest = Path('.config/mise/conf.d/chrono-harness.toml')
    original = tomllib.loads((host/manifest).read_text())['tools']['http:chrono-pr']
    subprocess.run(['mise', 'install', 'http:chrono-pr'], cwd=host, env=env, check=True)
    old, _, old_path = verified_install(host, env, original)
    old_digest = hashlib.sha256(old_path.read_bytes()).digest()
    git('merge', '--ff-only', upstream_dev, cwd=host)
    assert git('rev-parse', 'HEAD', cwd=host) == upstream_dev
    assert git('branch', '--show-current', cwd=host) == 'dev'
    tag = os.environ['COPIER_PREVIEW']
    candidate = os.environ['COPIER_SHA']
    refs = git('ls-remote', '--exit-code', 'https://github.com/chrono-harness/chrono-harness-copier.git', f'refs/tags/{tag}')
    assert refs.split() == [candidate, f'refs/tags/{tag}']
    run_copy(source, host, vcs_ref=candidate, defaults=True, overwrite=True, data={
        'repository':'chrono-harness/chrono-harness-example', 'dev_branch':'dev',
        'features':['pr'], 'tool_install_channels':'dev', 'local_check_retention':False,
        'manage_roadmap':False,
    })
    entry = ['sh','.chrono-harness/install-tools.sh']
    resolved = host/'.config/mise/conf.d/zz-chrono-harness-resolved.toml'
    setup = ['mise', 'run', 'harness-setup']
    for attempt, command in enumerate((entry, setup), start=1):
        subprocess.run(command, cwd=host, env=env, check=True)
        selected = tomllib.loads(resolved.read_text())['tools']['http:chrono-pr']
        current, preview, binary = verified_install(host, env, selected)
        assert preview and current != old and binary != old_path
        assert hashlib.sha256(binary.read_bytes()).digest() != old_digest
        assert current == newest_preview(), f'expected the latest public preview, installed {current}'
        subprocess.run(['python3', '-B', 'check.py'], cwd=host, env=env, check=True)
        print(f'{attempt=} old={old} current={current} {old_path.exists()=}', flush=True)
    # Keep the seed Release and asset URLs reachable. Reject only release-list HTTPS.
    tools = stage/'query-outage'
    tools.mkdir()
    curl = tools/'curl'
    actual_curl = shlex.quote(shutil.which('curl'))
    curl.write_text('#!/bin/sh\n' +
        'for url do\n' +
        '  case "$url" in https://api.github.com/repos/*/releases\\?*)\n' +
        '    echo "Release query sent during outage" >&2\n' +
        '    exec ' + actual_curl + ' --disable --noproxy api.github.com ' +
        '--connect-to api.github.com:443:127.0.0.1:1 "$@";;\n' +
        '  esac\ndone\nexec ' + actual_curl + ' "$@"\n')
    curl.chmod(0o755)
    unavailable = {**env, 'PATH': str(tools) + os.pathsep + env['PATH']}
    error = subprocess.run(setup, cwd=host, env=unavailable, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(error.stdout, flush=True)
    assert 'Release query sent during outage' in error.stdout, 'release query never reached the failure point'
    assert error.returncode != 0, 'installer succeeded on cached resolution during query failure'
    print(f'blocked release query returned {error.returncode} with cached tools on disk', flush=True)
