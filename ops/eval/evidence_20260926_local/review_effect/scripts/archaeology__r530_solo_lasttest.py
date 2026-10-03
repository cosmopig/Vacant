import json,glob,collections,re,sys
sys.path.insert(0,'/home/user/Vacant')
from vacant_network.trace.evidence import CLAIMS, RUNNERS, FAIL_OUT, PASS_OUT
TEST=re.compile(r"run_tests\.sh|pytest|unittest|tests_visible")
WRITE=re.compile(r"(cat\s*>|>\s*solution|tee |python3? - <<|sed -i|\bmv\b|\bcp\b|cat <<)")
res=collections.Counter(); detail=[]
for d in sorted(glob.glob('/home/user/Vacant/runs/g_r530_s*_[12]')):
    rows={}
    for l in open(d+'/rows.jsonl'):
        r=json.loads(l); rows[(r['task_id'],r['arm'])]=r
    ev=collections.defaultdict(list)
    for l in open(d+'/calls.jsonl'):
        c=json.loads(l)
        if c.get('kind')=='tool':
            ev[(c['task_id'],c['arm'])].append(('tool',c))
        elif c.get('role')=='r530':
            m=c.get('meta') or {}
            ev[(m.get('task_id'),m.get('arm'))].append(('llm',c))
    for (t,a),r in rows.items():
        if a!='A-SOLO': continue
        seq=ev.get((t,a),[])
        tests=[(i,c) for i,(k,c) in enumerate(seq) if k=='tool' and TEST.search(c.get('command') or '')]
        writes=[i for i,(k,c) in enumerate(seq) if k=='tool' and WRITE.search(c.get('command') or '') and 'solution' in (c.get('command') or '')]
        llm=[c for k,c in seq if k=='llm']
        final=(llm[-1].get('response') or '') if llm else ''
        claim=bool(CLAIMS.search(final))
        if not tests: cls='no_test_run'
        else:
            i,c=tests[-1]
            out=(c.get('stdout') or '')+(c.get('stderr') or '')
            failed = c.get('rc',0)!=0 or bool(FAIL_OUT.search(out))
            stale = any(w>i for w in writes)
            cls = 'last_test_failed' if failed else ('passed_then_edited' if stale else 'last_test_passed')
        key=(r['visible_all_pass'], cls, claim)
        res[key]+=1
        detail.append((d.split('/')[-1],t,r['visible_all_pass'],cls,claim,len(tests),len(llm)))
for k,v in sorted(res.items(), key=str): print(k,v)
print('meta keys sample:')
import itertools
shown=collections.Counter()
for d in sorted(glob.glob('/home/user/Vacant/runs/g_r530_s*_[12]')):
    rows={}
    for l in open(d+'/rows.jsonl'):
        r=json.loads(l); rows[(r['task_id'],r['arm'])]=r
    ev=collections.defaultdict(list)
    for l in open(d+'/calls.jsonl'):
        c=json.loads(l)
        if c.get('kind')=='tool': ev[(c['task_id'],c['arm'])].append(c)
    for (t,a),r in rows.items():
        if a!='A-SOLO': continue
        tests=[c for c in ev[(t,a)] if TEST.search(c.get('command') or '')]
        if not tests: continue
        c=tests[-1]; out=(c.get('stdout') or '')+(c.get('stderr') or '')
        failed = c.get('rc',0)!=0 or bool(FAIL_OUT.search(out))
        k=(r['visible_all_pass'],failed)
        if k in [(False,False),(True,True)] and shown[k]<3:
            shown[k]+=1
            print('====',k,d.split('/')[-1],t,'rc',c.get('rc'),'cmd:',(c.get('command') or '')[:150].replace('\n',' | '))
            print(out[-500:])
