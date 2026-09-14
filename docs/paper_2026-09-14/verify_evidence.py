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
(OUT/'verified_evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('CROSS',json.dumps(report['cross_primary']['pairs']))
print('RECEIPTS',len(chains),report['receipts']['entries'],'PASS')
