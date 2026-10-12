import json, collections, statistics as st, datetime as dt
L='/home/user/Vacant/ops/eval/evidence_20260926_local/formal/cells.json'
EXCL={'5','70'}
def ts(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
cells=json.load(open(L))
R={}
for c in cells:
    R[(c['task'],c['arm'],c['sample'])]=c
tasks=sorted({c['task'] for c in cells},key=int)
