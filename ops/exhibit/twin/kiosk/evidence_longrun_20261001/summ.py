import json,sys,statistics as st
def load(f): return [r for r in (json.loads(l) for l in open(f)) if 'min' in r]
def seg(rows,a,b): return [r for r in rows if a<=r['min']<b]
for f in ('before_base_exhibit-deploy-20260926.jsonl','after_fix-world3-longrun.jsonl'):
    rows=load(f); last=rows[-1]['min']
    print(f, 'rows',len(rows),'span_min',last)
    third=last/3
    for name,(a,b) in {'first third':(0,third),'mid':(third,2*third),'last third':(2*third,last+1)}.items():
        s=seg(rows,a,b)
        if not s: continue
        fps=[float(r['fps']) for r in s if r.get('fps')]
        print(f"  {name:11s} heapMB={st.mean(r['heapMB'] for r in s):.1f} rssMB={st.mean(r['rssMB'] for r in s if r.get('rssMB')):.0f} nodes={st.mean(r['nodes'] for r in s):.0f} listeners={st.mean(r['listeners'] for r in s):.0f} fps_med={st.median(fps):.1f} pending={st.mean(r['pending'] for r in s):.0f} seen={st.mean(r['seen'] for r in s):.0f} dropped_last={s[-1]['dropped']} navs={s[-1]['nav']}")
