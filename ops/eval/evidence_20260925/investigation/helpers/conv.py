import json,glob,os,re
J='/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/formal/jobs'
P='/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal'
runs=json.load(open(J+'/../analysis/runs.json'))
latest={}
for r in runs:
    k=(r['model'],r['arm'],r['task'])
    if k not in latest or r['job']>latest[k]['job']: latest[k]=r
def expected(t):
    s=open(f'{P}/dabstep-{t}/tests/test.sh').read()
    return s.split("<<'ANSWER_EOF'\n")[1].split('\nANSWER_EOF')[0]
pat=re.compile(r"[^.\n|]*(?:answer is|final answer|I'll output|I will output|the answer should be|So the answer|answer:|is the answer|answer would be|I'll go with|I will use)[^.\n|]*",re.I)
for k,r in sorted(latest.items(), key=lambda x:(x[0][0],x[0][1],int(x[0][2]))):
    if r['reward']==1.0: continue
    tdir=os.path.join(J,r['job'],r['trial'])
    so=open(os.path.join(tdir,'verifier/test-stdout.txt')).read()
    if 'answer.txt not found' not in so: continue
    A=[]
    for s in sorted(glob.glob(os.path.join(tdir,'agent/pi/sessions/*.jsonl'))):
        for l in open(s):
            o=json.loads(l); m=o.get('message')
            if not m or m.get('role')!='assistant': continue
            for x in (m.get('content') or []):
                if x.get('type') in ('thinking','text'): A.append(x.get('thinking') or x.get('text') or '')
    hits=[h.strip() for h in pat.findall('\n'.join(A))]
    print(f"## {k[0]} {k[1]} {k[2]} EXP={expected(k[2])[:60]!r}")
    for h in hits[-3:]: print('   -',h[:220])
