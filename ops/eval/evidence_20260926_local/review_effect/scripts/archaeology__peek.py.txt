import json,glob,collections,re
exec(open('/tmp/claude-0/review_effect/archaeology/r530_solo_lasttest2.py').read().split('res=collections.Counter()')[0])
n=0
for d in sorted(glob.glob('/home/user/Vacant/runs/g_r530_s*_[12]')):
    rows={}
    for l in open(d+'/rows.jsonl'):
        r=json.loads(l); rows[(r['task_id'],r['arm'])]=r
    ev=collections.defaultdict(list)
    for l in open(d+'/calls.jsonl'):
        c=json.loads(l)
        if c.get('kind')=='tool': ev[(c['task_id'],c['arm'])].append(c)
    for (t,a),r in rows.items():
        if a!='A-SOLO' or not r['visible_all_pass']: continue
        tools=ev[(t,a)]
        runs=[c for c in tools if RUN.search(c.get('command') or '') and not NOTRUN.match(c.get('command') or '')]
        if runs and runs[-1].get('rc',0)!=0 and n<4:
            n+=1; c=runs[-1]
            print('====',t,'rc',c['rc'],'gate_round',c.get('gate_round'),'| last tool cmd idx',tools.index(c),'of',len(tools))
            print((c.get('command') or '')[:300]); print('OUT:',((c.get('stdout') or '')+(c.get('stderr') or ''))[-300:])
