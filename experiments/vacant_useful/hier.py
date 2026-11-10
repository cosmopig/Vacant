import pickle,json,random,math,sys
import numpy as np
from collections import defaultdict
from sklearn.linear_model import LogisticRegression
sys.path.insert(0,'.')
from offline import wilson,mcn,boot,D,pids,S10,S20,items,Y,pr
rows=pickle.load(open(__import__('os').path.expanduser('~/.cache/vacant/twin2k500/')+'pricing_rows.pkl','rb'))
prods=sorted({r[1] for r in rows}); pi={q:i for i,q in enumerate(prods)}
lv=defaultdict(set)
for r in rows: lv[r[1]].add(r[3])
lvl={q:{v:i/(len(s)-1) for i,v in enumerate(sorted(s))} for q,s in lv.items()}
byp=defaultdict(dict)
for p,q,name,price,yes in rows: byp[p][q]=(lvl[q][price],int(yes))
def feat(q,l):
    x=np.zeros(len(prods)+2); x[pi[q]]=1; x[-2]=l; x[-1]=l*l; return x
def fitpop(train):
    X=[];y=[]
    for p in train:
        for q,(l,yy) in byp[p].items(): X.append(feat(q,l)); y.append(yy)
    return LogisticRegression(C=10,max_iter=1000).fit(np.array(X),np.array(y))
def person_shift(z_obs,y_obs,prior_var=1.0):
    b=0.0
    for _ in range(25):
        p=1/(1+np.exp(-(z_obs+b))); g=np.sum(y_obs-p)-b/prior_var; h=np.sum(p*(1-p))+1/prior_var; b+=g/h
    return b
# other (non-pricing) items: LOO pop majority
qi={q:i for i,q in enumerate(items)}
def evalset(test,train,Ks,seed=0):
    clf=fitpop(train); res={K:[] for K in Ks}
    trn=np.array([pr[p] for p in train])
    popm={q:(Y[trn,qi[q]][Y[trn,qi[q]]>=0]==0).mean() for q in items}
    for p in test:
        w4=D[p]['w4']; pq=list(byp[p])
        Z={q:clf.decision_function(feat(q,byp[p][q][0])[None])[0] for q in pq}
        for q,(lab,*_) in w4.items():
            y=0 if lab=='option_1' else 1  # 0 == option_1 == Yes
            itemmaj=0 if popm[q]>0.5 else 1
            for K in Ks:
                if q in byp[p]:
                    rng=random.Random(f'{seed}{p}{q}{K}'); others=[o for o in pq if o!=q]; rng.shuffle(others); obs=others[:K]
                    b=person_shift(np.array([Z[o] for o in obs]),np.array([byp[p][o][1] for o in obs])) if K else 0.0
                    pyes=1/(1+np.exp(-(Z[q]+b))); pred=0 if pyes>0.5 else 1
                else: pred=itemmaj
                res[K].append((p,q,pred,y,itemmaj))
    return res
Ks=(0,1,3,5,10,20,39)
allres={}
for name,S in (('S10',S10),('S20',S20)):
    allres[name]=evalset(S,[p for p in pids if p not in set(S)],Ks)
rng=random.Random(1); order=pids[:]; rng.shuffle(order); full={K:[] for K in Ks}
for f in range(5):
    fold=order[f::5]; r=evalset(fold,[p for p in pids if p not in set(fold)],Ks)
    for K in Ks: full[K]+=r[K]
allres['ALL_5FOLD']=full
pickle.dump(allres,open(__import__('os').path.expanduser('~/.cache/vacant/twin2k500/hier_results.pkl'),'wb'))
for name,res in allres.items():
    print('##',name,'(baseline = item-level population majority, ignores price)')
    for K in Ks:
        rows_=res[K]; c=[r[2]==r[3] for r in rows_]; bl=[r[4]==r[3] for r in rows_]; h=sum(c); n=len(c); lo,hi=wilson(h,n)
        b,cc,p=mcn(bl,c); bt=boot(bl,c,[r[0] for r in rows_],n=1000)
        print(f'K={K:2d} acc={h/n:.3f} ({h}/{n}) CI {lo:.3f}-{hi:.3f} base={sum(bl)/n:.3f} diff={(h-sum(bl))/n:+.3f} b={b} c={cc} McNemar p={p:.2g} boot95=[{bt[0]:+.3f},{bt[1]:+.3f}]')
