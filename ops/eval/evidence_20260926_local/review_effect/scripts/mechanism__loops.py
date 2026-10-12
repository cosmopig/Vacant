from common import *
import collections,re,json
def loop_turn(r, k=3):
    seen=collections.Counter()
    for t in r['turns'] or []:
        for c,o in zip(t['calls'],t['outs']):
            key=(c['name'], re.sub(r"\s+"," ",json.dumps(c.get('args'),sort_keys=True))[:400])
            seen[key]+=1
            okey=('out', o['text'][:300]) if o['text'].strip() and len(o['text'])<300 else None
            if okey: seen[okey]+=1
            if seen[key]>=k or (okey and seen[okey]>=k):
                return t['i']
    return None
def first_correct(r):
    k=ans_kind(r['expected'])
    if k not in ('num','str','list'): return 'nd'
    for t in r['turns'] or []:
        outs="\n".join(o['text'] for o in t['outs'])
        if contains_correct_strict(outs,r['expected'],k) or contains_correct_strict(t['text'],r['expected'],k): return t['i']
    return None
