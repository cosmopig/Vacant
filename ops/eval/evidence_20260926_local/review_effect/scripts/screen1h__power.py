"""Power of a paired A-vs-C screen: per pair P(C-only)=b+D, P(A-only)=b. Exact enumeration of the trinomial.
Tests: (1) exact McNemar two-sided alpha=.05 (conditional binomial on discordant pairs);
       (2) screening rule: one-sided exact sign test alpha=.10."""
from math import comb
from functools import lru_cache
@lru_cache(None)
def binom_tail_ge(n,k):  # P(X>=k), X~Bin(n,.5)
    return sum(comb(n,i) for i in range(k,n+1))/2**n
def mcnemar_two(w,l):
    n=w+l
    if n==0: return 1.0
    k=max(w,l); return min(1.0,2*binom_tail_ge(n,k))
def sign_one(w,l):
    n=w+l
    if n==0: return 1.0
    return binom_tail_ge(n,w)
def power(N,b,D,test,alpha):
    pw=b+D; pl=b; p0=1-pw-pl
    tot=0.0
    for w in range(N+1):
        for l in range(N-w+1):
            pr=comb(N,w)*comb(N-w,l)*pw**w*pl**l*p0**(N-w-l)
            if test(w,l)<=alpha: tot+=pr
    return tot
if __name__=='__main__':
    b=0.06
    print('b (A-only rate per pair) =',b)
    print('N   | McNemar 2-sided .05: D=.10 .15 .20 .25 | sign 1-sided .10: D=0(false go) .10 .15 .20 .25')
    for N in (20,24,30,36,40,48,60,77,100):
        m=[power(N,b,D,mcnemar_two,.05) for D in (.10,.15,.20,.25)]
        s=[power(N,b,D,sign_one,.10) for D in (0,.10,.15,.20,.25)]
        print(f'{N:3d} | '+' '.join(f'{x:.2f}' for x in m)+' | '+' '.join(f'{x:.2f}' for x in s))
    print('\nwhole-77-like mix (b=.06): D=.074 (observed C2) and .10/.15')
    for N in (40,77,154,231):
        print(N,[round(power(N,.06,D,mcnemar_two,.05),2) for D in (.074,.10,.15)],[round(power(N,.06,D,sign_one,.10),2) for D in (.074,.10,.15)])
