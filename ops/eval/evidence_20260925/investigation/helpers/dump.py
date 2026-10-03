# read-only transcript dumper (writes nothing)
import json,glob,os,sys
J='/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/formal/jobs'
runs=json.load(open(J+'/../analysis/runs.json'))
latest={}
for r in runs:
    k=(r['model'],r['arm'],r['task'])
    if k not in latest or r['job']>latest[k]['job']: latest[k]=r
model,arm,task=sys.argv[1:4]
TH=int(sys.argv[4]) if len(sys.argv)>4 else 400
TR=int(sys.argv[5]) if len(sys.argv)>5 else 1200
r=latest[(model,arm,task)]
tdir=os.path.join(J,r['job'],r['trial'])
print('DIR',tdir)
ses=sorted(glob.glob(os.path.join(tdir,'agent/pi/sessions/*.jsonl')))
for s in ses:
  print('SESSION',s)
  for i,l in enumerate(open(s),1):
    o=json.loads(l); m=o.get('message')
    if not m: continue
    role=m.get('role')
    if role=='system': continue
    cont=m.get('content')
    if isinstance(cont,str): cont=[{'type':'text','text':cont}]
    for c in cont or []:
        t=c.get('type')
        if t=='thinking': print(f'[L{i} {role} THINK] '+c.get('thinking','')[:TH].replace('\n',' | '))
        elif t=='text': print(f'[L{i} {role} TEXT] '+c.get('text','')[:(TR if role!="user" else 3000)])
        elif t=='toolCall': print(f'[L{i} {role} CALL {c.get("name")}] '+json.dumps(c.get('arguments'),ensure_ascii=False)[:2500])
        else: print(f'[L{i} {role} {t}]',str(c)[:300])
    if role=='assistant' and m.get('stopReason')!='toolUse': print(f'   stop={m.get("stopReason")} err={m.get("errorMessage")}')
