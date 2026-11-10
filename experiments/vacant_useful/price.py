import pickle,re,numpy as np
from collections import defaultdict
D=pickle.load(open(__import__('os').path.expanduser('~/.cache/vacant/twin2k500/')+'compact.pkl','rb'))
rows=[]
for p,d in D.items():
    for q,(lab,stem,opts,fam) in d['w4'].items():
        if not q.startswith('QID9_'): continue
        m=re.search(r'following product in that category: (.*?)\. The product is priced at: \$([0-9,.]+)',stem)
        rows.append((p,q,m.group(1),float(m.group(2).rstrip('.').replace(',','')),lab=='option_1'))
prod=defaultdict(list)
for r in rows: prod[r[2]].append(r[3])
print('products',len(prod),'rows',len(rows))
import statistics
k=list(prod)[:3]
for x in k: print(x, sorted(set(prod[x]))[:10], len(prod[x]))
med={k:statistics.median(v) for k,v in prod.items()}
rel=np.array([np.log(r[3]/med[r[2]]) for r in rows]); y=np.array([r[4] for r in rows])
for lo,hi in [(-9,-.2),(-.2,-.05),(-.05,.05),(.05,.2),(.2,9)]:
    m=(rel>=lo)&(rel<hi); print(lo,hi,m.sum(), y[m].mean() if m.sum() else None)
pickle.dump(rows,open(__import__('os').path.expanduser('~/.cache/vacant/twin2k500/')+'pricing_rows.pkl','wb'))
