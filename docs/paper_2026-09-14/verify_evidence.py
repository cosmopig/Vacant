"""Read-only recomputation from archived rows and public signed receipts.

No experiment analyzer imports, model calls, network, or sandbox re-execution.
"""
from pathlib import Path
import hashlib
import json
import math
from collections import defaultdict
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent

def inverse_cdf(k, n, target):
    lo,hi=0.,1.
    for _ in range(80):
        p=(lo+hi)/2
        cdf=sum(math.comb(n,i)*p**i*(1-p)**(n-i) for i in range(k+1))
        if cdf>target: lo=p
        else: hi=p
    return (lo+hi)/2

def paired(a, b):
    common = sorted(a.keys() & b.keys())
    yes = sum(a[t] and not b[t] for t in common)
    no = sum(b[t] and not a[t] for t in common)
    n, d = len(common), yes + no
    p = min(1., 2 * sum(math.comb(d, i) for i in range(min(yes, no) + 1)) / 2**d)
    lo = inverse_cdf(yes-1,d,.975) if yes else 0.
    hi = inverse_cdf(yes,d,.025) if no else 1.
    return dict(n=n,b=yes,c=no,delta_pp=100*(yes-no)/n,p_raw=p,
                conditional_ci_pp=[100*(2*lo-1)*d/n,100*(2*hi-1)*d/n])

def summarize(patterns, family):
    groups=defaultdict(dict); fd=defaultdict(int); sources=[]
    for pat in patterns:
        for f in sorted((ROOT/'runs').glob(pat+'/rows.jsonl')):
            sources.append(str(f.relative_to(ROOT)))
            for line in f.read_text().splitlines():
                r=json.loads(line); a=r['arm']; t=r['task_id']
                assert t not in groups[a], (f,a,t)
                groups[a][t]=bool(r['accepted'] and r['meets_demand'])
                fd[a]+=bool(r['accepted'] and not r['meets_demand'])
    pairs={a+'_vs_'+b:paired(groups[a],groups[b]) for a,b in family}
    floor=0.
    for i,(k,v) in enumerate(sorted(pairs.items(),key=lambda x:x[1]['p_raw'])):
        floor=max(floor,min(1.,(len(pairs)-i)*v['p_raw']));v['p_holm']=floor
    return dict(sources=sources,arms={a:dict(n=len(v),correct=sum(v.values()),false_delivery=fd[a]) for a,v in groups.items()},pairs=pairs),groups

family=[(a,b) for a in ['HPI','HOC','HMIX'] for b in ['OFF','CONFORM']]
report={}
for key,pat in [('R460','g_r460_harness_lcb2_*')]+[(f'r{i}',f'g_r460r{i}_harness_lcb2_*') for i in range(1,6)]:
    report[key],_=summarize([pat],family)
    print(key,json.dumps(report[key]['pairs']['HMIX_vs_CONFORM']))
cross={}; merged=defaultdict(dict)
for key,pat in [('LCB3_medium','g_r529_lcb3m_*'),('LCB3_hard','g_r529_lcb3h_*'),('HumanEvalPlus','g_r529_hep_*'),('MBPPPlus','g_r529_mbpp_*')]:
    cross[key],g=summarize([pat],[('HMIX','CONFORM'),('HMIX','OFF')])
    for a,rows in g.items():
        assert not (merged[a].keys() & rows.keys()); merged[a].update(rows)
report['cross_sets']=cross
report['cross_primary'],_=summarize(['g_r529_lcb3m_*','g_r529_lcb3h_*','g_r529_hep_*','g_r529_mbpp_*'],[('HMIX','CONFORM'),('HMIX','OFF')])
chains=[]
for pat in ['g_r460r*_harness_lcb2_*','g_r529_*']:
    for run in sorted((ROOT/'runs').glob(pat)):
        for f in sorted(run.glob('receipts_*.ndjson')):
            pk=json.loads(f.with_suffix('.pub.json').read_text())['pub_hex']
            pub=Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk)); prev='0'*64; stream=None; branch=None
            entries=[json.loads(l) for l in f.read_text().splitlines()]
            assert entries
            for i,e in enumerate(entries,1):
                core={k:v for k,v in e.items() if k!='sig'}
                raw=json.dumps(core,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
                assert e['seq']==i and e['prev_hash']==prev
                assert e['stream_id']==('0'*64 if i==1 else stream)
                if branch is not None: assert e['branch_id']==branch
                pub.verify(bytes.fromhex(e['sig']),raw)
                prev=hashlib.sha256(raw).hexdigest()
                if i==1: stream=prev;branch=e['branch_id']
            chains.append(dict(path=str(f.relative_to(ROOT)),n=len(entries),head=prev,sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
report['receipts']=dict(chains=len(chains),entries=sum(c['n'] for c in chains),failed=0,details=chains)
assert report['receipts']['chains']==194 and report['receipts']['entries']==9841
assert [report[f'r{i}']['pairs']['HMIX_vs_CONFORM']['b'] for i in range(1,6)]==[15,17,12,13,14]
assert [report[f'r{i}']['pairs']['HMIX_vs_CONFORM']['c'] for i in range(1,6)]==[8,12,11,10,9]
assert all(report[f'r{i}']['pairs'][a+'_vs_OFF']['p_holm']<.05 for i in range(1,6) for a in ['HPI','HOC','HMIX'])
assert report['cross_primary']['pairs']['HMIX_vs_CONFORM']['b']==31
assert report['cross_primary']['pairs']['HMIX_vs_CONFORM']['c']==23
report['scope']='Recomputed archived outcome labels, exact binomial McNemar, within-run Holm, conditional intervals, and public receipt signatures. Does not regenerate or re-execute code, verify hidden-test quality, or establish completeness of the published log.'

# --- token ledger (new keys only; nothing above this line is recomputed) -------
# Same per-task, per-arm summation of calls.jsonl usage that writes
# verified_tokens.json, embedded here so the cost numbers cited in the paper sit
# in the same artifact as the outcome numbers and cannot drift apart.
import verify_tokens as VT
TOK=VT.build_report()
report['tokens']=TOK
report['token_crosscheck']=VT.crosscheck(TOK)
assert not report['token_crosscheck']['mismatches'],report['token_crosscheck']['mismatches']

def arm_cell(run,arm):
    v=TOK[run]['arms'][arm]
    return {k:v[k] for k in ['calls','probe_calls','reported_total','prompt_tokens','completion_tokens',
        'reasoning_tokens','valid_total','void_total','unmetered_calls','n','correct',
        'per_task','per_task_excl_probe','per_task_incl_void','tpc_valid','tpc_all',
        'reasoning_pct_of_completion']}
REPS=['R460','r1','r2','r3','r4','r5'];SETS=['LCB3_medium','LCB3_hard','HumanEvalPlus','MBPPPlus']
head={'reps':{},'cross_sets':{},'cross_backends':{},'cross_pooled':{}}
for k in REPS:
    head['reps'][k]={'arms':{a:arm_cell(k,a) for a in ['OFF','CONFORM','OFF5','HPI','HOC','HMIX']},
        'OFF5_over_CONFORM':TOK[k]['arm_ratios']['OFF5_over_CONFORM'],
        'HMIX_over_CONFORM':TOK[k]['arm_ratios']['HMIX_over_CONFORM'],
        'HMIX_over_OFF5':TOK[k]['arm_ratios']['HMIX_over_OFF5']}
for k in SETS+['cross_pooled']:
    bucket=head['cross_pooled'] if k=='cross_pooled' else head['cross_sets']
    bucket[k]={'arms':{a:arm_cell(k,a) for a in ['OFF','CONFORM','HMIX']},
        'HMIX_over_CONFORM':TOK[k]['arm_ratios']['HMIX_over_CONFORM']}
    if k!='cross_pooled':
        for mode in ['reasoning','no_reasoning']:
            key=k+'_'+mode
            head['cross_backends'][key]={'arms':{a:arm_cell(key,a) for a in ['OFF','CONFORM','HMIX']},
                'HMIX_over_CONFORM':TOK[key]['arm_ratios']['HMIX_over_CONFORM']}
head['inference_mode_same_bank']=TOK['reasoning_mode_audit']
head['decision_cost_conditions']={
 'R460_condition_iii_tpc_over_OFF5':{k:TOK[k]['arm_ratios']['HMIX_over_OFF5']['tpc_incl_void'] for k in REPS},
 'R529_cost_condition_pooled_tpc_HMIX_over_CONFORM':TOK['cross_pooled']['arm_ratios']['HMIX_over_CONFORM']['tpc_incl_void'],
 'note':'R460 and its five repetitions require tokens per correct delivery, void calls included, no higher than OFF5 in the same run. R529 replaces that with pooled tokens per correct delivery of H-MIX no higher than CONFORM. Both are reproduced here from the recomputed ledger, not copied from the stage analyzers.'}
head['caliber']=('Every figure is reported prompt plus completion tokens. reasoning_tokens is a subset of '
 'completion and is never added again. per_task divides valid-task tokens by that arm valid tasks and '
 'includes arm-attributed wire_probe; per_task_excl_probe removes probe tokens from the same numerator; '
 'per_task_incl_void and tpc_all keep void and failed-but-metered calls. Failed calls with no usage are '
 'unknown cost, never zero. r5 denominators differ per arm (OFF 119, CONFORM 117, OFF5 118, HPI 120, '
 'HOC 120, HMIX 119). R529 per-set absolute tokens mix two inference conditions and must be read per backend.')
report['tokens_headline']=head
(OUT/'verified_evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('CROSS',json.dumps(report['cross_primary']['pairs']))
print('RECEIPTS',len(chains),report['receipts']['entries'],'PASS')
print('TOKENS crosscheck cells',report['token_crosscheck']['cells'],'mismatches',len(report['token_crosscheck']['mismatches']))
