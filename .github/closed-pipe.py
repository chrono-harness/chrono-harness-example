import os,subprocess as sp,sys
tool=sys.argv[1]
normal=sp.run([tool,'report-v1'],input=b'{',capture_output=True)
assert normal.returncode==2 and normal.stdout==b'' and b'EOF' in normal.stderr and normal.stderr.endswith(b'\n')
reader,writer=os.pipe()
os.close(reader)
try:
 closed=sp.run([tool,'report-v1'],input=b'{',stdout=sp.PIPE,stderr=writer)
finally:
 os.close(writer)
assert closed.returncode==2 and closed.stdout==b''
print('CLOSED_PIPE_EXIT',normal.returncode,closed.returncode)
