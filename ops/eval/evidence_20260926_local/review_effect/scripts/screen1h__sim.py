"""Monte Carlo makespan of a screen on local compute using run_batch.plan() and empirical per-task durations."""
import sys, random, statistics as st, heapq
sys.path.insert(0,'/home/user/Vacant/ops/eval/local')
from run_batch import plan
from load import *
Lc=local(); Pd=paid(); allt=sorted(Lc,key=int)
def Ap(t):
    a=[Lc[t][('A',s)] for s in (1,2,3)]
    return dict(nofile=sum(not x['f'] for x in a), correct=sum(x['r'] for x in a), wrong=sum(x['f'] and x['r']==0 for x in a), dur=st.mean(x['d'] for x in a))
U=[t for t in allt if Ap(t)['nofile']>=1 and Ap(t)['dur']<=300]
K=[t for t in allt if Ap(t)['correct']==3 and Ap(t)['dur']<=300]
W=[t for t in allt if Ap(t)['wrong']>=1 and Ap(t)['dur']<=300 and t not in U]
# machine factor
def durs(t, armtype, up):
    arms=('A',) if armtype=='A' else ('C1','C2')
    d=[Lc[t][(a,s)]['d'] for a in arms for s in (1,2,3) if Lc[t][(a,s)]['up']==up]
    return d
wv=[x['d'] for t in allt for k,x in Lc[t].items() if x['up']=='w401']; ov=[x['d'] for t in allt for k,x in Lc[t].items() if x['up']=='1003']
def draw(rng,t,armtype,up):
    d=durs(t,armtype,up)
    if d: return rng.choice(d)+5
    other='1003' if up=='w401' else 'w401'
    f=(st.median(wv)/st.median(ov)) if up=='w401' else (st.median(ov)/st.median(wv))
    return rng.choice(durs(t,armtype,other))*f+5
def makespan(tasks, samples, arms=('A','C'), ups={'w401':3,'1003':1}, reps=2000, seed=1):
    cells=plan(tasks, list(arms), samples, 20260927, ups)
    rng=random.Random(seed); out=[]
    for _ in range(reps):
        fin=0
        for up,conc in ups.items():
            q=[c for c in cells if c[3]==up]
            slots=[0.0]*conc
            for c in q:
                s=heapq.heappop(slots); e=s+draw(rng,c[0],'A' if c[1]=='A' else 'C',up); heapq.heappush(slots,e); fin=max(fin,e)
        out.append(fin/60)
    out.sort()
    return len(cells), st.median(out), out[int(.9*len(out))]
def api_makespan(tasks, samples, pairs=3, reps=2000, seed=2):
    rng=random.Random(seed); out=[]; cost=[]
    order=[(t,s) for s in samples for t in tasks]
    for _ in range(reps):
        slots=[0.0]*pairs; fin=0; c=0
        for t,s in order:
            a=Pd[t][('g4','A')]; cc=Pd[t][('g4','C')]
            # jitter: resample pair wall from same task's A/C walls +/- 25%
            w=max(a['d'],cc['d'])*rng.uniform(.75,1.25)+10
            st_=heapq.heappop(slots); heapq.heappush(slots,st_+w); fin=max(fin,st_+w)
            c+=(a['cost'] or 0)+(cc['cost'] or 0)
        out.append(fin/60); cost.append(c)
    out.sort()
    return st.median(out), out[int(.9*len(out))], st.mean(cost)
if __name__=='__main__':
    rs=random.Random(20260927)
    K12=sorted(rs.sample(K,12),key=int)
    print('K12 (random.Random(20260927).sample(K,12))',K12)
    designs={
     'D1 U24x1 + K12x1 (36 pairs)':(U+K12,[1]),
     'D2 U24x2 (48 pairs)':(U,[1,2]),
     'D3 U24x1 + K12x1 + W9x1 (45 pairs)':(U+K12+W,[1]),
     'D4 random 40 of 77 x1':(sorted(random.Random(7).sample(allt,40),key=int),[1]),
     'D5 all 77 x1':(allt,[1]),
     'D6 U24x1 only':(U,[1]),
    }
    for name,(ts_,sm) in designs.items():
        n,med,p90=makespan(ts_,sm)
        am,ap90,ac=api_makespan(ts_,sm,pairs=3)
        am2,ap902,_=api_makespan(ts_,sm,pairs=2)
        print(f'{name:38s} runs {n:3d} | local makespan median {med:5.1f} min p90 {p90:5.1f} | API(g4 think-on) 3 pairs: {am:5.1f}/{ap90:5.1f} min, 2 pairs: {am2:5.1f}/{ap902:5.1f} min, cost ${ac:.2f}')
