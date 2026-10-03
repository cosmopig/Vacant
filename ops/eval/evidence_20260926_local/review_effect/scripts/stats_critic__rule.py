from math import comb
def tri(N,pw,pl):
    p0=1-pw-pl; out={}
    for w in range(N+1):
        for l in range(N-w+1):
            out[(w,l)]=comb(N,w)*comb(N-w,l)*pw**w*pl**l*p0**(N-w-l)
    return out
def netdist(N,pw,pl):
    d={}
    for (w,l),p in tri(N,pw,pl).items(): d[w-l]=d.get(w-l,0)+p
    return d
def one_stage(N,pw,pl,go=4):
    d=netdist(N,pw,pl); return sum(p for k,p in d.items() if k>=go)
def two_stage(N,pw,pl,go1=4,stop1=1,go2=6):
    d=netdist(N,pw,pl); tot=0
    for k,p in d.items():
        if k>=go1: tot+=p
        elif k>stop1:
            tot+=p*sum(q for k2,q in d.items() if k+k2>=go2)
    return tot
def exp_runs(N,pw,pl,stop1=1,go1=4):
    d=netdist(N,pw,pl); return sum(p for k,p in d.items() if stop1<k<go1)
