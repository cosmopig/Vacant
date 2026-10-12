import json, re, glob, os, sys
D='/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/analysis_runs/'
HDR="psp_reference,merchant,card_scheme,year,hour_of_day,minute_of_hour,day_of_year,is_credit,eur_amount,ip_country,issuing_country,device_type,ip_address,email_address,card_number,shopper_interaction,card_bin,has_fraudulent_dispute,is_refused_by_adyen,aci,acquirer_country".split(',')
COLTOK={c:c.split('_') for c in HDR}
STOP=set(sys.argv[1].split(',')) if len(sys.argv)>1 and sys.argv[1] else set()
QONLY = len(sys.argv)>2 and sys.argv[2]=='q'
def sing(w):
    if len(w)<=3: return w
    if w.endswith('ies'): return w[:-3]+'y'
    if w.endswith('sses') or w.endswith('shes') or w.endswith('ches') or w.endswith('xes'): return w[:-2]
    if w.endswith('s') and not w.endswith('ss'): return w[:-1]
    return w
def named_cols(text):
    words=[sing(w) for w in re.findall(r"[a-z0-9]+", text.lower())]
    # also literal column names
    lits={c for c in HDR if "_" in c and re.search(r"\b"+c+r"\b", text)}
    out={}
    for n in (3,2,1):
        for i in range(len(words)-n+1):
            g=words[i:i+n]
            if n==1 and g[0] in STOP: continue
            hits=[c for c,t in COLTOK.items() if any(t[j:j+n]==g for j in range(len(t)-n+1))]
            if len(hits)==1:
                out.setdefault(hits[0], ' '.join(g))
    for c in lits: out.setdefault(c,c)
    return out
def parse(f):
    txt=open(D+f).read()
    req=txt.split('## Request',1)[1].split('## Turn 1',1)[0]
    if QONLY:
        m=re.search(r'question you need to answer:(.*)', req); req=m.group(1)
    calls=[]
    for m in re.finditer(r'^## Turn (\d+).*?(?=^## )', txt, re.S|re.M):
        t=int(m.group(1)); body=m.group(0)
        for cm in re.finditer(r'^call (\w+): (\{.*\})$', body, re.M):
            try: a=json.loads(cm.group(2))
            except Exception: a={'raw':cm.group(2)}
            calls.append((t,cm.group(1),a))
    return req,calls,txt
def selected(col, calls):
    idx=HDR.index(col)+1
    for t,k,a in calls:
        s=a.get('command') or a.get('content') or ''
        if col in s: return 'name'
        if 'payments.csv' in s or k=='write':
            if re.search(r'cut\s[^|]*-f\s*'+str(idx)+r'\b', s) or re.search(r'cut\s[^|]*-f[0-9,]*\b'+str(idx)+r'\b', s): return 'cut'
            if re.search(r'\$'+str(idx)+r'\b', s) and 'awk' in s: return 'awk'
    for t,k,a in calls:
        s=a.get('command') or a.get('content') or ''
        if re.search(r'pandas|pd\.|import csv|csv\.|\.py\b', s): return 'failopen'
    return None
idx=json.load(open(D+'index.json'))
for r in idx:
    req,calls,txt=parse(r['file'])
    nc=named_cols(req)
    uses_pay=any('payments.csv' in (a.get('command') or '') for _,_,a in calls)
    miss=[(c,p) for c,p in nc.items() if selected(c,calls) is None]
    fire = uses_pay and r['answer_file'] and miss
    print(f"{r['file']:26s} R={r['reward']} file={r['answer_file']!s:5} pay={uses_pay!s:5} named={sorted(nc.items())} MISS={miss if fire else ''}")
