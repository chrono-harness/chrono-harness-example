from pathlib import Path
import hashlib,platform,re,subprocess,sys
host,output,tag=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
arch='macos-aarch64' if platform.system()=='Darwin' else 'linux-x86_64'
s=(host/'.config/mise/conf.d/chrono-harness.toml').read_text().split('[tools."http:chrono-host-release"]')[1].split('\n\n')[0]
assert 'version = "'+tag[1:]+'"' in s
line,=[l for l in s.splitlines() if '/chrono-host-release-'+arch+'"' in l]
url,expected=re.search(r'url = "([^"]+)".*checksum = "sha256:([a-f0-9]{64})"',line).groups()
assert '/'+tag+'/' in url;subprocess.run(['curl','--fail','--silent','--show-error','--location',url,'--output',output],check=True)
assert hashlib.sha256(output.read_bytes()).hexdigest()==expected;output.chmod(0o755)
