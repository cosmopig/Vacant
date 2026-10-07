import json,glob,re,collections,sys
ABS=("渴望","靜默","虛無","細碎","共振","壓抑","沉默","溫潤","圓潤")
STOP=set("一個 這個 他的 的是 我的 自己 沒有 不是 就是 可以 因為 所以 但是 然後 已經 還是 它的 什麼 我們 一種 這種 那個 如果 一點 一些 的地 在這 的東 西的 的一 了一 的不 他在 到了 的人".split())
def texts(d,names=("v1","v2","v3","v4","v5","v6","v7","v8")):
    out=[]
    for n in names:
        r=json.load(open(f"{d}/{n}.json"))
        out+= [r.get('letter_full') or '', r.get('plan_full') or '', r.get('record_full') or '']+list((r.get('made_things') or {}).values())
    return "\n".join(out)
def stats(s):
    c={w:s.count(w) for w in ABS}
    bg=collections.Counter(s[i:i+2] for i in range(len(s)-1) if re.fullmatch(r"[一-鿿]{2}",s[i:i+2]))
    # 排除世界物件與地名、虛詞
    world=set()
    import pathlib
    for p in pathlib.Path("/Users/cosmopig/Documents/GitHub/Vacant-wt-p13/ops/exhibit/twin/world/materials").rglob("*.txt"):
        t=p.stem
        world|={t[i:i+2] for i in range(len(t)-1)}
    for pl in "投遞口 捏土處 長桌廣場 石頭閘門 帳本鏈 草稿角 紙卡地 畫架與長椅 世界 地上 這個 一個 他的 我的 自己 沒有 不是 就是 可以 因為 所以 然後 已經 還是 什麼 這是 的是 做的 我自 己做 他在 一種 不具 一點 這種".split():
        world|={pl[i:i+2] for i in range(len(pl)-1)}
    top=[(k,v) for k,v in bg.most_common(200) if k not in world and not re.search(r"[的了在是和與不也就都有我他你它這那]",k)][:10]
    return c,top,len(s)
for label,d in (("跑前(第二輪，修之前)", "/tmp/out8b"),("跑後(本輪)", "/tmp/out12")):
    c,top,n=stats(texts(d))
    print(label,"字數",n,"\n 抽象詞:",c,"合計",sum(c.values()),"\n top10 重複詞(2字):",top)
