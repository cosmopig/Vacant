import sys, re, glob, json
sys.path.insert(0,'/home/user/Vacant')
from vacant_network.trace.evidence import RUNNERS
S='/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/local/formal_v3'
files=glob.glob(S+'/**/agent/pi.txt',recursive=True)
print('pi.txt files',len(files))
hit=0; ex=[]
for f in files:
    found=False
    for line in open(f,errors='replace'):
        if 'toolCall' not in line: continue
        try: e=json.loads(line)
        except Exception: continue
        m=(e.get('message') or {})
        for c in m.get('content') or []:
            if isinstance(c,dict) and c.get('type')=='toolCall' and c.get('name')=='bash':
                cmd=str((c.get('arguments') or {}).get('command'))
                if RUNNERS.search(cmd): found=True; ex.append((f.split('/')[-4],cmd[:120]))
        if found: break
    hit+=found
print('runs with a bash tool call matching RUNNERS:',hit); print(ex[:5])
