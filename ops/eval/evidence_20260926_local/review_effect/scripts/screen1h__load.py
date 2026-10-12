import json, datetime as dt, collections
L='/home/user/Vacant/ops/eval/evidence_20260926_local/formal/cells.json'
P='/home/user/Vacant/ops/eval/evidence_20260925/formal/runs.json'
EXCL={'5','70'}
def ts(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def local():
    cells=json.load(open(L))
    T=collections.defaultdict(dict)
    for c in cells:
        d=(ts(c['finished'])-ts(c['started'])).total_seconds() if c['started'] and c['finished'] else None
        T[c['task']][(c['arm'],c['sample'])]=dict(r=int(c['reward'] or 0), f=bool(c['answer_file']), n=c['requests'], d=d, up=c['upstream'])
    return {t:v for t,v in T.items() if t not in EXCL}
def paid():
    r=json.load(open(P))
    T=collections.defaultdict(dict)
    # take latest per (task, model, arm) by job name
    for x in sorted(r,key=lambda x:x['job']):
        T[x['task']][(x['model'],x['arm'])]=dict(r=int(x['reward'] or 0), n=x['requests'], cost=x['cost_usd'], d=(ts(x['finished'])-ts(x['started'])).total_seconds() if x['started'] and x['finished'] else None)
    return {t:v for t,v in T.items() if t not in EXCL}
