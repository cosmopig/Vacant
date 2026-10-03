import sys, math
sys.path.insert(0, "/tmp/claude-0/verify_formal")
from load import load
from stats import *
rows,_=load(); tasks77=[t for t in sorted({k[0] for k in rows},key=int) if t not in ("5","70")]
d=[float(v) for v in per_task_diffs(rows,"A","C2",tasks77,[1,2,3]).values()]
n=len(d); m=sum(d)/n; sd=(sum((x-m)**2 for x in d)/(n-1))**.5; t=m/(sd/n**.5); v=n-1
dens=lambda x: math.gamma((v+1)/2)/(math.sqrt(v*math.pi)*math.gamma(v/2))*(1+x*x/v)**(-(v+1)/2)
N=200000; a,b=abs(t),60.0; h=(b-a)/N
s=dens(a)+dens(b)+sum((4 if i%2 else 2)*dens(a+i*h) for i in range(1,N))
print("paired t=%.4f df=%d two-sided p=%.4f; mean=%.4f 95%%CI t: [%.4f, %.4f]"%(t,v,2*s*h/3,m,m-1.9917*sd/n**.5,m+1.9917*sd/n**.5))
