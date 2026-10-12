# read-only: characterise no-answer runs
import json,glob,os,re,sys
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
out=[]
for k,r in sorted(latest.items(), key=lambda x:(x[0][0],x[0][1],int(x[0][2]))):
    if r['reward']==1.0: continue
    tdir=os.path.join(J,r['job'],r['trial'])
    so=open(os.path.join(tdir,'verifier/test-stdout.txt')).read()
    if 'answer.txt not found' not in so: continue
    exp=expected(k[2])
    ses=sorted(glob.glob(os.path.join(tdir,'agent/pi/sessions/*.jsonl')))
    tool_txt=[];asst_txt=[];errs=0;calls=[];bigreads=0;last_think=''
    for s in ses:
        for l in open(s):
            o=json.loads(l); m=o.get('message')
            if not m: continue
            c=m.get('content'); c=[{'type':'text','text':c}] if isinstance(c,str) else (c or [])
            if m.get('role')=='toolResult':
                if m.get('isError'): errs+=1
                tool_txt+= [x.get('text','') for x in c if x.get('type')=='text']
            if m.get('role')=='assistant':
                for x in c:
                    if x.get('type')=='thinking': asst_txt.append(x['thinking']); last_think=x['thinking']
                    if x.get('type')=='text': asst_txt.append(x['text'])
                    if x.get('type')=='toolCall':
                        a=x.get('arguments',{}); calls.append(x['name']+':'+json.dumps(a)[:80])
                        if x['name']=='read' and any(f in json.dumps(a) for f in ('payments.csv','fees.json')): bigreads+=1
    T='\n'.join(tool_txt); A='\n'.join(asst_txt)
    # did the expected answer appear?
    hit_tool=hit_asst=False
    en=scorer.extract_numeric(exp) if re.fullmatch(r'-?[\d.]+',exp.strip()) else None
    if en is not None:
        for src,name in ((T,'tool'),(A,'asst')):
            for mm in re.findall(r'-?\d+\.\d+|-?\d+',src):
                try:
                    if scorer.compare_numeric(abs(float(mm)),abs(en)) and abs(float(mm))>0:
                        if name=='tool': hit_tool=True
                        else: hit_asst=True
                        break
                except: pass
    else:
        ex=exp.strip()
        if ',' in ex:
            items=[i.strip() for i in ex.split(',')]
            def has(src):
                nums=set(re.findall(r'\b\d+\b',src)) if all(i.isdigit() for i in items) else None
                return ex in src
            hit_tool= ex in T; hit_asst= ex in A
        else:
            hit_asst = re.search(r'\b'+re.escape(ex)+r'\b',A) is not None
            hit_tool = re.search(r'\b'+re.escape(ex)+r'\b',T) is not None
    out.append(dict(model=k[0],arm=k[1],task=k[2],req=r['requests'],exp=exp[:40],errs=errs,bigreads=bigreads,ncalls=len(calls),hit_tool=hit_tool,hit_asst=hit_asst,last=last_think[-260:].replace('\n',' | ')))
for o in out: print(json.dumps(o,ensure_ascii=False))
