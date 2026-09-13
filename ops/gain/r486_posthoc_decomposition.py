import json, statistics
from collections import Counter
snap=json.load(open('ops/gain/data/r486_gateway_snapshot_v2.json'))
rows=snap['rows']; events=snap['events']
chat=[r for r in rows if "chat/completions" in (r.get("path") or "")]
def iv(r,h):
    d=r["latency_ms"]/1000.0
    return (r["ts"], r["ts"]+d) if h=="start" else (r["ts"]-d, r["ts"])
MAIN="100.124.254.83"
tg=[r for r in chat if r["latency_ms"]>=600000 and "gemma" in (r.get("model") or "")]
print("targets:",len(tg))

def union_within(others,s,e):
    segs=[(max(a,s),min(b,e)) for a,b in others if min(b,e)>max(a,s)]
    if not segs: return 0.0
    segs.sort(); tot=0.0; ca,cb=segs[0]
    for a,b in segs[1:]:
        if a>cb: tot+=cb-ca; ca,cb=a,b
        else: cb=max(cb,b)
    return tot+(cb-ca)

for h in ("start","end"):
    print(f"\n=== hypo={h} : overlap decomposition per target ===")
    for r in tg:
        s,e=iv(r,h); L=e-s
        own=[iv(o,h) for o in chat if o["id"]!=r["id"] and o.get("client_ip")==MAIN]
        frn=[iv(o,h) for o in chat if o["id"]!=r["id"] and o.get("client_ip")!=MAIN]
        print(f"  id={r['id']} len={L/60:6.1f}min  own_client={union_within(own,s,e)/L:.3f}"
              f"  foreign={union_within(frn,s,e)/L:.3f}")

# distinct foreign rows
frn_rows=[r for r in chat if r.get("client_ip")!=MAIN]
print("\nforeign chat rows (by ip):",len(frn_rows),
      " of which model!=gemma:",sum(1 for r in frn_rows if "gemma" not in (r.get("model") or "")))
print("gemma-model rows from foreign ip:",sum(1 for r in frn_rows if "gemma" in (r.get("model") or "")))
print("non-gemma rows from MAIN ip:",sum(1 for r in chat if r.get("client_ip")==MAIN and "gemma" not in (r.get("model") or "")))
print("foreign models:",Counter(r.get("model") for r in frn_rows))

# reload base rate
w0=min(r["ts"] for r in rows); w1=max(r["ts"] for r in rows)
ev=[e for e in events if e.get("machine")=="1004" and e.get("event") in ("loaded","unloaded") and w0<=e["ts"]<=w1]
print(f"\nload/unload events inside snapshot window: {len(ev)}  window={(w1-w0)/3600:.2f}h"
      f"  => mean gap {(w1-w0)/max(1,len(ev))/60:.1f} min")
print("event kinds:",Counter(e["event"] for e in ev))
short=[r for r in chat if r["latency_ms"]<600000]
for h in ("start",):
    hit=sum(1 for r in short if any(iv(r,h)[0]<=x["ts"]<iv(r,h)[1] for x in ev))
    print(f"  base rate: short chat requests spanning a load/unload event: {hit}/{len(short)}"
          f" = {hit/len(short):.4f}   (median short len {statistics.median(x['latency_ms'] for x in short)/1000:.1f}s)")
    # duration-matched expectation: P(interval of length L contains >=1 event) under Poisson rate
    rate=len(ev)/(w1-w0)
    import math
    exp_tg=statistics.mean(1-math.exp(-rate*(iv(r,h)[1]-iv(r,h)[0])) for r in tg)
    print(f"  Poisson expectation that a target-length interval contains an event: {exp_tg:.3f}")

# concurrency time-share
for h in ("start","end"):
    evs=[]
    for r in chat:
        a,b=iv(r,h); evs.append((a,1)); evs.append((b,-1))
    evs.sort(key=lambda x:(x[0],x[1]))
    cur=0; last=None; t={}
    for ts_,d in evs:
        if last is not None and ts_>last: t[cur]=t.get(cur,0.0)+(ts_-last)
        cur+=d; last=ts_
    tot=sum(t.values())
    print(f"\nhypo={h} concurrency time-share (of {tot/3600:.2f}h spanned):",
          {k:f"{v/tot:.3f}" for k,v in sorted(t.items())})
