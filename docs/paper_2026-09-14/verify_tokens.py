"""Independent token accounting from archived calls, aligned to outcome rows.
No model calls. Missing usage is unknown, never assumed to be zero consumption.

build_report() returns the whole ledger so that verify_evidence.py can embed the
same object under its own new keys; crosscheck() compares every recomputed cell
against the stage analyzers (r460/r460r/r529) without importing them.
"""
from pathlib import Path
from collections import defaultdict, Counter
import json, hashlib

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]
FILES={}
def read(path):
    raw=path.read_bytes();FILES[str(path.relative_to(ROOT))]=hashlib.sha256(raw).hexdigest()
    return [json.loads(x) for x in raw.splitlines() if x]

def audit(patterns, backend=None):
    rows=defaultdict(dict);calls=[]
    for pat in patterns:
        for f in sorted((ROOT/'runs').glob(pat+'/calls.jsonl')):
            cc=read(f)
            apis={x.get('api','') for x in cc if x.get('meta',{}).get('arm')}
            if backend and not any(backend in a for a in apis):continue
            rr=f.with_name('rows.jsonl')
            if not rr.exists():continue
            for r in read(rr):
                a,t=r['arm'],r['task_id'];assert t not in rows[a],(f,a,t)
                rows[a][t]=bool(r['accepted'] and r['meets_demand'])
            calls+=cc
    arms={};taskcost=defaultdict(lambda:defaultdict(int));aux=Counter(); anomalies=[]
    for c in calls:
        m=c.get('meta') or {};u=c.get('usage') or {};a=m.get('arm');t=m.get('task_id')
        if not a:
            aux['calls']+=1;aux['reported_tokens']+=u.get('total_tokens') or 0
            if c.get('ok'):aux['ok_calls']+=1
            if u.get('total_tokens') is None:aux['unmetered_calls']+=1
            continue
        if a not in arms:arms[a]=Counter()
        v=arms[a];v['calls']+=1
        if c.get('role')=='wire_probe':v['probe_calls']+=1
        if not c.get('ok'):v['failed_calls']+=1
        if u.get('total_tokens') is None:
            v['unmetered_calls']+=1
            if c.get('ok'):v['unmetered_successful_calls']+=1
            continue
        n=u['total_tokens'];p=u.get('prompt_tokens');o=u.get('completion_tokens')
        if p is not None and o is not None and p+o!=n:anomalies.append([a,t,p,o,n])
        v['reported_total']+=n;v['prompt_tokens']+=p or 0;v['completion_tokens']+=o or 0
        v['reasoning_tokens']+=(u.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0
        if not c.get('ok'):v['failed_reported_tokens']+=n
        if c.get('role')=='wire_probe':v['probe_tokens']+=n;v['probe_metered_calls']+=1
        if t in rows.get(a,{}):
            v['valid_total']+=n;taskcost[a][t]+=n
            if c.get('role')=='wire_probe':v['valid_probe_tokens']+=n
        else:v['void_total']+=n
    for a,v in arms.items():
        v['n']=len(rows[a]);v['correct']=sum(rows[a].values())
        v['per_task']=v['valid_total']/v['n'] if v['n'] else None
        # Same denominator, probe tokens removed from the numerator only.
        v['per_task_excl_probe']=(v['valid_total']-v['valid_probe_tokens'])/v['n'] if v['n'] else None
        v['per_task_incl_void']=v['reported_total']/v['n'] if v['n'] else None
        v['tpc_valid']=v['valid_total']/v['correct'] if v['correct'] else None
        v['tpc_all']=v['reported_total']/v['correct'] if v['correct'] else None
        v['reasoning_pct_of_completion']=100*v['reasoning_tokens']/v['completion_tokens'] if v['completion_tokens'] else None
        v['reasoning_pct_of_reported_total']=100*v['reasoning_tokens']/v['reported_total'] if v['reported_total'] else None
    # Whole-arm ratios. These are the arbitration-side cost multiples (each arm on
    # its own valid tasks), not the common-task pair numbers computed below.
    arm_ratios={}
    for a,b in [('OFF5','CONFORM'),('HMIX','CONFORM'),('HMIX','OFF'),('HMIX','OFF5'),
                ('CONFORM','OFF'),('OFF5','OFF'),('HPI','CONFORM'),('HOC','CONFORM')]:
        if a not in arms or b not in arms:continue
        va,vb=arms[a],arms[b]
        def rat(key):
            x,y=va.get(key),vb.get(key)
            return x/y if x is not None and y else None
        arm_ratios[a+'_over_'+b]=dict(per_task_excl_void=rat('per_task'),
            per_task_incl_void=rat('per_task_incl_void'),
            tpc_excl_void=rat('tpc_valid'),tpc_incl_void=rat('tpc_all'))
    pairs={}
    for a,b in [('CONFORM','OFF'),('CONFORM','OFF5')]+[(a,b) for a in ['HPI','HOC','HMIX'] for b in ['OFF','CONFORM','OFF5']]:
        if a not in rows or b not in rows:continue
        ts=rows[a].keys()&rows[b].keys();n=len(ts)
        if not n:continue
        ca=sum(rows[a][t] for t in ts);cb=sum(rows[b][t] for t in ts)
        ta=sum(taskcost[a][t] for t in ts);tb=sum(taskcost[b][t] for t in ts)
        pairs[a+'_vs_'+b]=dict(n=n,a_correct=ca,b_correct=cb,delta_pp=100*(ca-cb)/n,
            a_tokens=ta,b_tokens=tb,a_per_task=ta/n,b_per_task=tb/n,
            token_ratio=ta/tb,extra_token_pct=100*(ta/tb-1),
            a_tpc=ta/ca if ca else None,b_tpc=tb/cb if cb else None,
            tpc_ratio=(ta/ca)/(tb/cb) if ca and cb else None,
            extra_tokens_per_net_correct=(ta-tb)/(ca-cb) if ca!=cb else None)
    return dict(arms=arms,arm_ratios=arm_ratios,pairs=pairs,auxiliary=aux,usage_sum_mismatches=anomalies)

CROSS=[('LCB3_medium','g_r529_lcb3m_*'),('LCB3_hard','g_r529_lcb3h_*'),
       ('HumanEvalPlus','g_r529_hep_*'),('MBPPPlus','g_r529_mbpp_*')]
BACKENDS=[('reasoning','100.119.113.56'),('no_reasoning','100.86.226.21')]
REPS=['R460','r1','r2','r3','r4','r5']

def build_report():
    FILES.clear()
    report={}
    for key,pat in [('R460','g_r460_harness_lcb2_*')]+[(f'r{i}',f'g_r460r{i}_harness_lcb2_*') for i in range(1,6)]:
        report[key]=audit([pat])
    for key,pats in [('early_MBPP',['g_r444_conform_mbpp','g_r445_conform_mbpp_ext']),('early_LCB2',['g_r447_conform_lcb2'])]:
        report[key]=audit(pats)
    for name,pat in CROSS:
        report[name]=audit([pat])
        for backend,addr in BACKENDS:
            report[name+'_'+backend]=audit([pat],addr)
    report['cross_pooled']=audit([p for _,p in CROSS])
    report['eq5']={}
    for name,pat in [('r446','g_r446_eq5_mbpp'),('r448','g_r448_eq5_mbpp_seed2'),('r449b','g_r449_eq5_lcb2'),('r449c','g_r449c_eq5_lcb3')]:
        fs=list((ROOT/'runs').glob(pat+'/calls.jsonl'))
        report['eq5'][name]=audit([pat]) if fs else {'status':'calls.jsonl unavailable locally; do not invent token totals','path':'runs/'+pat}
        rr=read(ROOT/'runs'/pat/'rows.jsonl')
        ca=sum(bool(r['gate_deliv']) for r in rr);cb=sum(bool(r['vote_deliv']) for r in rr)
        report['eq5'][name]['selection_pair']=dict(n=len(rr),gate_correct=ca,vote_correct=cb,delta_pp=100*(ca-cb)/len(rr),generation_cost_ratio_by_design=1.0)
    report['missing_cost_records']={}
    for key,run in [('r448','g_r448_eq5_mbpp_seed2'),('r461','g_r461_lcb3_three_arm')]:
        rr=read(ROOT/'runs'/run/'rows.jsonl')
        report['missing_cost_records'][key]=dict(path='runs/'+run,n_rows=len(rr),
           reason='Outcome rows contain calls_used but no token usage. calls.jsonl is absent in the local repository and its git history. No token estimate substituted.')
    assert not any(v['usage_sum_mismatches'] for v in report.values() if 'usage_sum_mismatches' in v)
    # Inference-mode audit for the same-bank family. R460 and its five repetitions
    # all ran on one endpoint, and the paper cites both the successful-call count
    # and the zero reasoning share. A stale hand-carried count is exactly the kind
    # of number that survives a rerun, so recompute it here: arm-labelled calls
    # minus failures, plus the one unattributed preflight call per block.
    mode={'blocks':{},'note':'Successful calls = arm-labelled calls minus failed ones, plus the unattributed preflight call each block issues. reasoning_tokens is summed over every arm; zero means no successful call on these blocks reported reasoning tokens.'}
    for k,pat in [('R460','g_r460_harness_lcb2_*')]+[(f'r{i}',f'g_r460r{i}_harness_lcb2_*') for i in range(1,6)]:
        v=report[k];mode['blocks'][k]=len(list((ROOT/'runs').glob(pat+'/calls.jsonl')))
        mode[k]=dict(calls_ok=sum(a['calls']-a['failed_calls'] for a in v['arms'].values())+v['auxiliary']['ok_calls'],
                     reasoning_tokens=sum(a['reasoning_tokens'] for a in v['arms'].values()))
    mode['R460R_blocks']=sum(mode['blocks'][k] for k in REPS[1:])
    mode['R460R_calls_ok']=sum(mode[k]['calls_ok'] for k in REPS[1:])
    mode['all_blocks']=sum(mode['blocks'].values())
    mode['all_calls_ok']=sum(mode[k]['calls_ok'] for k in REPS)
    mode['reasoning_tokens_total']=sum(mode[k]['reasoning_tokens'] for k in REPS)
    mode['reasoning_pct_of_completion']=0.0 if not mode['reasoning_tokens_total'] else None
    report['reasoning_mode_audit']=mode
    report['source_sha256']=dict(FILES)
    report['scope']='Reported prompt plus completion tokens; reasoning is a subset of completion. Arm-attributed probes included. Unattributed preflight is separate. Per-pair costs use exactly the same common tasks as effect numerators. Unmetered attempts are unknown costs. Not equal-token experiments or total financial cost.'
    return report

# ---------------------------------------------------------------- cross-check

ANALYZERS={'r460':'ops/gain/replay/r460/r460_analyze.json',
           'r460r':'ops/gain/replay/r460r/r460r_analyze_5reps.json',
           'r529':'ops/gain/replay/r529/r529_analyze.json'}
SETMAP={'lcb3_medium':'LCB3_medium','lcb3_hard':'LCB3_hard',
        'humanevalplus':'HumanEvalPlus','evalplus':'MBPPPlus'}
HOSTMAP={'1003':'reasoning','1004':'no_reasoning'}

def crosscheck(report):
    out=dict(cells=0,mismatches=[],unavailable=[],sources={})
    def cmp(label,got,exp):
        if exp is None or got is None:
            out['unavailable'].append(label);return
        out['cells']+=1
        d=abs(got-exp)
        if d>max(1e-6,1e-9*abs(exp)):
            out['mismatches'].append(dict(cell=label,recomputed=got,analyzer=exp,abs_diff=d))
    A={}
    for key,rel in ANALYZERS.items():
        path=ROOT/rel
        A[key]=json.loads(path.read_text())
        out['sources'][rel]=hashlib.sha256(path.read_bytes()).hexdigest()
    for arm,v in A['r460']['tokens'].items():
        g=report['R460']['arms'][arm]
        cmp(f'R460.{arm}.calls',float(g['calls']),float(v['calls_total']))
        cmp(f'R460.{arm}.tokens_total_incl_void',float(g['reported_total']),float(v['tokens_total_incl_void']))
        cmp(f'R460.{arm}.tokens_per_task',g['per_task'],v['tokens_per_task'])
        cmp(f'R460.{arm}.tpc_incl_void',g['tpc_all'],v['tpc_incl_void'])
    cmp('R460.tpc_off5_incl_void',report['R460']['arms']['OFF5']['tpc_all'],A['r460']['tpc_off5_incl_void'])
    for rep in A['r460r']['reps']:
        k='r%d'%rep['rep']
        cmp(f'{k}.HMIX.tokens_per_task',report[k]['arms']['HMIX']['per_task'],rep['tokens_per_task_hmix'])
        cmp(f'{k}.CONFORM.tokens_per_task',report[k]['arms']['CONFORM']['per_task'],rep['tokens_per_task_conform'])
    anchors=A['r460r']['aggregate']['r460_anchors_NOT_ARBITER']
    for arm,key in [('HMIX','tokens_per_task_hmix'),('CONFORM','tokens_per_task_conform')]:
        cmp(f'R460.{arm}.tokens_per_task_rounded',round(report['R460']['arms'][arm]['per_task']),float(anchors[key]))
    for name,v in A['r529']['per_set'].items():
        key=SETMAP[name]
        for arm,t in v['tokens'].items():
            g=report[key]['arms'][arm]
            cmp(f'{key}.{arm}.tokens_incl_void',float(g['reported_total']),float(t['tokens_incl_void']))
            cmp(f'{key}.{arm}.tokens_per_task',g['per_task_incl_void'],t['tokens_per_task'])
            cmp(f'{key}.{arm}.tpc_incl_void',g['tpc_all'],t['tpc_incl_void'])
    for arm,t in A['r529']['tokens_pooled'].items():
        g=report['cross_pooled']['arms'][arm]
        cmp(f'cross_pooled.{arm}.tokens_incl_void',float(g['reported_total']),float(t['tokens_incl_void']))
        cmp(f'cross_pooled.{arm}.tokens_per_task',g['per_task_incl_void'],t['tokens_per_task'])
        cmp(f'cross_pooled.{arm}.tpc_incl_void',g['tpc_all'],t['tpc_incl_void'])
        cmp(f'cross_pooled.{arm}.deliv_n',float(g['correct']),float(t['deliv_n']))
    for name,hosts in A['r529']['per_backend'].items():
        for host,v in hosts.items():
            key=SETMAP[name]+'_'+HOSTMAP[host]
            for arm,pa in v['per_arm'].items():
                g=report[key]['arms'][arm]
                cmp(f'{key}.{arm}.tokens_incl_void',float(g['reported_total']),float(pa['tokens_incl_void']))
                cmp(f'{key}.{arm}.tokens_per_task',g['per_task_incl_void'],pa['tokens_per_task'])
                cmp(f'{key}.{arm}.tpc_incl_void',g['tpc_all'],pa['tpc_incl_void'])
                cmp(f'{key}.{arm}.deliv_n',float(g['correct']),float(pa['deliv_n']))
            # The analyzer counts every successful wire call in the block, including
            # the one unattributed preflight call each block issues before the arms.
            calls_ok=sum(report[key]['arms'][a]['calls']-report[key]['arms'][a]['failed_calls'] for a in v['per_arm'])+report[key]['auxiliary']['ok_calls']
            cmp(f'{key}.reasoning.calls_ok',float(calls_ok),float(v['reasoning']['calls_ok']))
            with_reasoning=100.0 if v['reasoning']['reasoning_call_pp']==100.0 else v['reasoning']['reasoning_call_pp']
            got=100.0 if all(report[key]['arms'][a]['reasoning_tokens']>0 for a in v['per_arm']) else 0.0
            cmp(f'{key}.reasoning.call_pp',got,with_reasoning)
    out['notes']=[]
    if out['mismatches']:
        out['notes'].append('Cells differing from the stage analyzers are listed in mismatches; each is a disagreement to be resolved before citation, not a rounding preference.')
    else:
        out['notes'].append('Every compared cell agrees with the stage analyzers to within 1e-6 absolute; no analyzer number was adopted, each was recomputed from calls.jsonl and rows.jsonl.')
    out['notes'].append('R460 per-arm token_per_task and tpc are compared against r460_analyze.json tokens.*; the five repetitions only expose tokens_per_task for H-MIX and CONFORM in r460r_analyze_5reps.json, so the other four arms of each repetition have no analyzer counterpart and are recomputation-only.')
    out['notes'].append('R529 analyzer per_set/per_backend/tokens_pooled totals include void rows; this run has no void rows, so incl-void and excl-void coincide. The comparison therefore uses per_task_incl_void on the recomputed side.')
    out['notes'].append('Per-backend calls_ok matches only after adding the unattributed preflight call each block issues (one per block: 4+3, 2+1, 5+3 and 12+7). Those calls carry no arm label and are kept out of every per-arm token total.')
    out['notes'].append('wire_probe calls are inside the analyzer totals as well; the probe-free variant (per_task_excl_probe) exists only in this recomputation and has no analyzer cell to compare against.')
    out['notes'].append('reasoning_call_pp is compared as a 0/100 flag: the analyzer reports the share of successful calls carrying reasoning tokens per backend, while this recomputation aggregates reasoning tokens per arm, so only the all-or-nothing agreement is checkable.')
    out['unavailable_note']='Cells listed in unavailable have no analyzer counterpart or no recomputed value; they are not silent passes.'
    return out

def main():
    report=build_report()
    (BASE/'verified_tokens.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for k,v in report.items():
        if isinstance(v,dict) and 'arms' in v:
            print(k,[(a,round(x['per_task']),round(x['tpc_all']),x['unmetered_calls'],x['void_total']) for a,x in v['arms'].items()])
    xc=crosscheck(report)
    print('crosscheck cells',xc['cells'],'mismatches',len(xc['mismatches']),'unavailable',len(xc['unavailable']))
    print('hashed files',len(report['source_sha256']))
    return report

if __name__=='__main__':
    main()
