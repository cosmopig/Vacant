import json,sys,re,glob,hashlib
def norm(d):
    s=json.dumps(d,sort_keys=True)
    s=re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}','UUID',s)
    s=re.sub(r'[0-9a-f]{64}','HEX64',s)
    s=re.sub(r'(toolu_\w+|msg_\w+|session_\w+)','ID',s)
    s=re.sub(r'\d{4}-\d\d-\d\dT[\d:.]+Z?','TS',s)
    return s
def load(d):
    return [norm(json.load(open(f))) for f in sorted(glob.glob(d+'/bodies/*.json'))]
a,b=load(sys.argv[1]),load(sys.argv[2])
print(sys.argv[1],len(a),'vs',sys.argv[2],len(b))
for i,(x,y) in enumerate(zip(a,b)):
    print(' req',i+1,'identical' if x==y else 'DIFFERENT', hashlib.sha256(x.encode()).hexdigest()[:10], hashlib.sha256(y.encode()).hexdigest()[:10], len(x),len(y))
