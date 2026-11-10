import pickle,json,math,random,sys
import numpy as np
from collections import Counter,defaultdict
from scipy.stats import binomtest
from sklearn.linear_model import LogisticRegression
D=pickle.load(open(__import__('os').path.expanduser('~/.cache/vacant/twin2k500/')+'compact.pkl','rb'))
pids=sorted(D)
S10=json.load(open(__import__('os').environ.get('TWIN_S10','/workspace/vacant-twin2k-10')+'/manifest.json'))['pids']
S20=json.load(open(__import__('os').environ.get('TWIN_S20','/workspace/vacant-twin2k-20')+'/manifest.json'))['pids']
# features: one-hot (qid,answer) with >=20 people
cnt=Counter((q,a[0]) for p in pids for q,a in D[p]['calib'].items())
feats=[k for k,v in cnt.items() if v>=20 and v<=len(pids)-20]
fi={k:i for i,k in enumerate(feats)}
X=np.zeros((len(pids),len(feats)),dtype=np.float32)
for r,p in enumerate(pids):
    for q,a in D[p]['calib'].items():
        j=fi.get((q,a[0]))
        if j is not None: X[r,j]=1
items=sorted({q for p in pids for q in D[p]['w4']})
Y=np.full((len(pids),len(items)),-1,dtype=np.int8)
ii={q:i for i,q in enumerate(items)}
for r,p in enumerate(pids):
    for q,(lab,*_) in D[p]['w4'].items(): Y[r,ii[q]]=0 if lab=='option_1' else 1
print('people',len(pids),'features',len(feats),'items',len(items),'labelled cells',(Y>=0).sum(),file=sys.stderr)
pr={p:i for i,p in enumerate(pids)}
def predict(test_rows,train_rows,method,k=50):
    P=np.full((len(test_rows),len(items)),-1.0)
    tr=np.array(train_rows); te=np.array(test_rows)
    if method=='POP_MAJ':
        for j in range(len(items)):
            y=Y[tr,j]; y=y[y>=0]; P[:,j]=y.mean() if len(y) else .5
    elif method=='KNN':
        Xn=X/np.maximum(np.linalg.norm(X,axis=1,keepdims=True),1e-9)
        sim=Xn[te]@Xn[tr].T
        for a in range(len(te)):
            nn=np.argsort(-sim[a])[:k]
            for j in range(len(items)):
                y=Y[tr[nn],j]; w=sim[a][nn][y>=0]; y=y[y>=0]
                P[a,j]=(w*y).sum()/w.sum() if len(y) else .5
    elif method=='LOGREG':
        for j in range(len(items)):
            m=Y[tr,j]>=0; y=Y[tr,j][m]
            if len(set(y))<2: P[:,j]=y.mean() if len(y) else .5; continue
            clf=LogisticRegression(C=0.05,max_iter=300).fit(X[tr][m],y)
            P[:,j]=clf.predict_proba(X[te])[:,1]
    return P
def evaluate(test_pids,method,folds=None):
    te=[pr[p] for p in test_pids]
    tr=[i for i in range(len(pids)) if pids[i] not in set(test_pids)]
    P=predict(te,tr,method)
    out=[]
    for a,r in enumerate(te):
        for j in range(len(items)):
            if Y[r,j]>=0: out.append((pids[r],items[j],int(P[a,j]>0.5) if P[a,j]!=0.5 else -1,int(Y[r,j]),float(P[a,j])))
    return out
def wilson(h,n,z=1.96):
    p=h/n; d=1+z*z/n; c=p+z*z/(2*n); s=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return (c-s)/d,(c+s)/d
def mcn(a,b):
    # a,b lists of correct bools paired
    bb=sum(1 for x,y in zip(a,b) if y and not x); cc=sum(1 for x,y in zip(a,b) if x and not y)
    p=binomtest(bb,bb+cc,.5).pvalue if bb+cc else 1.0
    return bb,cc,p
def boot(a,b,people,n=2000,seed=0):
    rng=random.Random(seed); byp=defaultdict(list)
    for (x,y,p) in zip(a,b,people): byp[p].append(y-x)
    ks=list(byp); res=[]
    for _ in range(n):
        s=[v for k in (rng.choice(ks) for _ in ks) for v in byp[k]]; res.append(sum(s)/len(s))
    res.sort(); return res[int(.025*n)],res[int(.975*n)]
if __name__=='__main__':
    results={}
    # stored LOO majority among 10 from run
    import glob
    for name,S in (('S10',S10),('S20',S20)):
        res={m:evaluate(S,m) for m in ('POP_MAJ','KNN','LOGREG')}
        # within-sample LOO majority (as current Vacant baseline)
        loo=[]
        idx=[pr[p] for p in S]
        for r in idx:
            for j in range(len(items)):
                if Y[r,j]<0: continue
                others=[Y[o,j] for o in idx if o!=r and Y[o,j]>=0]
                m=sum(others)/len(others) if others else .5
                loo.append((pids[r],items[j],int(m>.5) if m!=.5 else -1,int(Y[r,j]),m))
        res['LOO_MAJ_SAMPLE']=loo
        results[name]=res
    # full 5-fold CV over all people
    rng=random.Random(1); order=pids[:]; rng.shuffle(order)
    full={m:[] for m in ('POP_MAJ','KNN','LOGREG')}
    for f in range(5):
        fold=order[f::5]
        for m in full: full[m]+=evaluate(fold,m)
    results['ALL_5FOLD']=full
    pickle.dump(results,open(__import__('os').path.expanduser('~/.cache/vacant/twin2k500/offline_results.pkl'),'wb'))
    for name,res in results.items():
        base='LOO_MAJ_SAMPLE' if 'LOO_MAJ_SAMPLE' in res else 'POP_MAJ'
        keys=[(r[0],r[1]) for r in res[base]]
        bmap={(r[0],r[1]):r[2]==r[3] for r in res[base]}
        print('##',name,'baseline=',base,'n=',len(keys))
        for m,rows in res.items():
            c=[r[2]==r[3] for r in rows]; h=sum(c); n=len(c); lo,hi=wilson(h,n)
            bl=[bmap[(r[0],r[1])] for r in rows]
            b,cc,p=mcn(bl,c); bt=boot(bl,c,[r[0] for r in rows]) if m!=base else (0,0)
            print(f'{m:16s} acc={h/n:.3f} ({h}/{n}) CI {lo:.3f}-{hi:.3f}  vs {base}: diff={(h-sum(bl))/n:+.3f} b={b} c={cc} p={p:.2g} boot95=[{bt[0]:+.3f},{bt[1]:+.3f}]')
