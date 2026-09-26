import json,glob,os,re,sys,io,contextlib
sys.path.insert(0,'/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal/dabstep-3/tests')
import scorer
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
def score(a,e):
    f=io.StringIO()
    with contextlib.redirect_stdout(f):
        try: return bool(scorer.question_scorer(a,e))
        except Exception as ex: return False
cand=re.compile(r"(?:answer is|final answer is|final answer seems to be|I'll output|I will output|answer should be|So the answer is|I'll go with|is the answer|Final Answer is|I will use)\s*[:\"'`]*([^\"'`\n|]{1,120}?)[\"'`]*(?:\.\s|\.$|\n|\||$| because| as | using)",re.I)
rows=[]
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
    e=expected(k[2])
    cs=[c.strip().strip('`"\'.') for c in cand.findall('\n'.join(A))]
    cs=[c for c in cs if c and len(c)<120]
    ok=[c for c in cs if score(c,e)]
    last=cs[-1] if cs else None
    rows.append((k,e[:30],len(cs),ok[-1] if ok else None,last, score(last,e) if last else None))
for x in rows: print(x)
