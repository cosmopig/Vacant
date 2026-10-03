import json,glob,os,re,sys
J='/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/formal/jobs'
runs=json.load(open(J+'/../analysis/runs.json'))
latest={}
for r in runs:
    k=(r['model'],r['arm'],r['task'])
    if k not in latest or r['job']>latest[k]['job']: latest[k]=r
for spec in sys.argv[1:]:
    m,a,t,needle=spec.split(':',3)
    r=latest[(m,a,t)]; tdir=os.path.join(J,r['job'],r['trial'])
    for s in sorted(glob.glob(os.path.join(tdir,'agent/pi/sessions/*.jsonl'))):
        for i,l in enumerate(open(s),1):
            o=json.loads(l); mm=o.get('message')
            if not mm or mm.get('role')!='assistant': continue
            for x in (mm.get('content') or []):
                txt=x.get('thinking') or x.get('text') or ''
                for mt in re.finditer(re.escape(needle),txt):
                    print(f"{m} {a} {t} L{i}: ...{txt[max(0,mt.start()-200):mt.end()+120]}...".replace('\n',' | '))
                    break
