import json,re,sys,hashlib,pathlib
def norm(p):
    s=pathlib.Path(p).read_text()
    s=re.sub(r'(ses|msg|prt|call|chatcmpl)_[A-Za-z0-9_]+','ID',s)
    s=re.sub(r'\d{4}-\d\d-\d\dT[\d:.]+Z?','TS',s)
    return s
def cmp(a,b):
    fa=sorted(pathlib.Path(a,'bodies').glob('*.json')); fb=sorted(pathlib.Path(b,'bodies').glob('*.json'))
    out=[f"{a} ({len(fa)} reqs) vs {b} ({len(fb)} reqs)"]
    for x,y in zip(fa,fb):
        nx,ny=norm(x),norm(y)
        same=nx==ny
        out.append(f"  {x.name} vs {y.name}: {'IDENTICAL' if same else 'DIFFERENT'} ({len(nx)} vs {len(ny)} bytes, sha {hashlib.sha256(nx.encode()).hexdigest()[:10]} / {hashlib.sha256(ny.encode()).hexdigest()[:10]})")
        if not same:
            import difflib
            d=list(difflib.unified_diff(nx.replace(',',',\n').splitlines(),ny.replace(',',',\n').splitlines(),lineterm='',n=0))
            out+=["    "+l[:200] for l in d[:12]]
    return "\n".join(out)
if __name__=="__main__": print(cmp(sys.argv[1],sys.argv[2]))
