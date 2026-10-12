import json,glob,collections,re,sys
sys.path.insert(0,'/home/user/Vacant')
from vacant_network.trace.evidence import CLAIMS, FAIL_OUT
RUN=re.compile(r"(^|[;&|]\s*|\s)(sh|bash|\./)\s*run_tests\.sh|pytest|python3? -m unittest|python3? (-m \w+ )?tests_visible/\S+\.py")
NOTRUN=re.compile(r"^\s*(cat|sed -n|head|tail|less|grep)\b")
WRITE_SOL=re.compile(r"solution\.py|> *solution|solution/")
WRITE_VERB=re.compile(r"cat\s*<<|cat\s*>|>\s*\S|tee |sed -i|python3? - ?<<|python3? -c|\bmv\b|\bcp\b|open\(")
TOUCH_TESTS=re.compile(r"(cat\s*<<[^\n]*>\s*|>\s*|tee\s+|sed -i[^\n]*)tests_visible/")
res=collections.Counter(); tt=collections.Counter(); res2=collections.Counter()
for d in sorted(glob.glob('/home/user/Vacant/runs/g_r530_s*_[12]')):
    rows={}
    for l in open(d+'/rows.jsonl'):
        r=json.loads(l); rows[(r['task_id'],r['arm'])]=r
    ev=collections.defaultdict(list)
    for l in open(d+'/calls.jsonl'):
        c=json.loads(l)
        if c.get('kind')=='tool': ev[(c['task_id'],c['arm'])].append(('tool',c))
        elif c.get('role')=='r530':
            m=c.get('meta') or {}
            ev[(m.get('task_id'),m.get('arm'))].append(('llm',c))
    for (t,a),r in rows.items():
        if a!='A-SOLO': continue
        seq=ev.get((t,a),[])
        tools=[c for k,c in seq if k=='tool']
        llm=[c for k,c in seq if k=='llm']
        final=(llm[-1].get('response') or '') if llm else ''
        claim=bool(CLAIMS.search(final))
        runs=[(i,c) for i,c in enumerate(tools) if RUN.search(c.get('command') or '') and not NOTRUN.match(c.get('command') or '')]
        EDIT=re.compile(r"(>\s*|tee\s+)(?!tests_visible/)[\w./-]+\.py\b|sed -i|open\([^)]*['\"]w|write_text|cat\s*<<[^\n]*>\s*(?!tests_visible/)[\w./-]+\.py")
        edits=[i for i,c in enumerate(tools) if EDIT.search(c.get('command') or '')]
        touched=any(TOUCH_TESTS.search(c.get('command') or '') for c in tools)
        if not runs: cls='no_run'
        else:
            i,c=runs[-1]; out=(c.get('stdout') or '')+(c.get('stderr') or '')
            failed=c.get("rc",0)!=0
            stale=any(e>i for e in edits)
            cls=('last_run_FAILED' if failed else 'last_run_passed')+('+edited_after' if stale else '')
        res[(r['visible_all_pass'],cls)]+=1
        hc=r.get('hidden_total',0)>0 and r['hidden_passed']==r['hidden_total']
        flag=cls in ('last_run_FAILED','last_run_FAILED+edited_after')
        res2[(flag,cls=='no_run',hc)]+=1
        if touched: tt[r['visible_all_pass']]+=1
        if not r['visible_all_pass']: res[('visfail_claim',claim)]+=1
for k,v in sorted(res.items(), key=str): print(k,v)
print('SOLO cells where agent wrote into tests_visible/ (by visible_all_pass):',dict(tt))

print('(flag_failed_or_stale, no_run, hidden_correct):',sorted(res2.items(),key=str))
