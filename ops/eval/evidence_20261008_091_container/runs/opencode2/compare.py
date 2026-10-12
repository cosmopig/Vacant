import json, sys, re, hashlib
def load(p):
    return [json.loads(l)["body"] for l in open(p) if l.strip()]
def norm(b):
    s = json.dumps(b, sort_keys=True, ensure_ascii=False)
    s = re.sub(r"ses_[A-Za-z0-9]+", "ses_X", s)
    s = re.sub(r"(msg|prt|call|toolu|chatcmpl)_[A-Za-z0-9_]+", r"\1_X", s)
    s = re.sub(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun) [A-Z][a-z]{2} \d{1,2} \d{4}\b", "DATE", s)
    return s
a, b = load(sys.argv[1]), load(sys.argv[2])
print("n_requests", len(a), len(b))
for i, (x, y) in enumerate(zip(a, b)):
    nx, ny = norm(x), norm(y)
    same = nx == ny
    print(f"req {i+1}: identical_after_id_normalisation={same} bytes={len(nx)}/{len(ny)} sha={hashlib.sha256(nx.encode()).hexdigest()[:12]}/{hashlib.sha256(ny.encode()).hexdigest()[:12]}")
    if not same:
        import difflib
        for l in list(difflib.unified_diff(json.dumps(json.loads(nx),indent=1).splitlines(), json.dumps(json.loads(ny),indent=1).splitlines(), lineterm="", n=0))[:20]:
            print("   ", l[:200])
