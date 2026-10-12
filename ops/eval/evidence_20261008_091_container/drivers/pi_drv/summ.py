import json,glob,os,sys
for d in sorted(glob.glob('/tmp/claude-0/e2e091/evidence/pi/*_*_*')):
    n=os.path.basename(d)
    rq=[json.loads(l) for l in open(d+'/mock.jsonl') if l.strip()] if os.path.exists(d+'/mock.jsonl') else []
    fb=[r for r in rq if r.get('feedback')]
    ans=[f for f in os.listdir(d) if f.startswith('answer_')]
    dm=glob.glob(d+'/dot_vacant/trace/projects/*/delivery.md')
    ev=glob.glob(d+'/dot_vacant/trace/projects/*/events.jsonl')
    print(n,'| reqs',len(rq),'| fed_back reqs',len(fb),'| answers',ans,'| delivery.md',len(dm),'| events',len(ev))
