#!/usr/bin/env python3
"""前後對照：cards_before.json（mirror 第一版，30 張）vs cards_r7.json（mirror2）。輸出分布表與兩條目標是否達成。
用法：python3 analyze_r7.py > compare.txt"""
import collections, json, pathlib, re
H = pathlib.Path(__file__).resolve().parent
TAG = re.compile(r"（第 \d+ 步）$")
START = ("還沒決定要做什麼", "先去看了一眼", "先把要做的事寫下來", "沒寫計畫，直接", "第一個動手翻的")
def norm(l):
    l = re.sub(r"\d+( 分 \d+)?", "N", TAG.sub("", l))     # 數字一律當 N：同一種句型換個數字不算不同句
    return "最後做出來的是《標題》" if l.startswith("最後做出來的是") else l
def stat(cards):
    c = collections.Counter(); bad = []
    for x in cards:
        ls = [norm(l) for l in x["lines"]]
        c.update(set(ls))
        if not any(not l.startswith(START) and not l.startswith("最後做出來的是") for l in ls):
            bad.append(x["id"])
    return c, bad
def main():
    b = json.load(open(H / "cards_before.json")); a = json.load(open(H / "cards_r7.json"))
    out = []
    for name, cards in (("前（mirror 第一版）", b), ("後（mirror2）", a)):
        c, bad = stat(cards); n = len(cards)
        top = c.most_common(1)[0]
        out += [f"## {name}：{n} 張；不同的句子 {len(c)} 種；最常見一句 {top[1]}/{n}＝{top[1]/n:.0%}（{top[0]}）",
                f"   每張至少一句不是開頭方式／最後做出來的是：不合格 {len(bad)} 張 {bad}",
                f"   有任何一句超過 1/3：{'是' if top[1] > n/3 else '否'}", ""]
        out += [f"{k:3d}  {v}" for v, k in [(s_, c_) for s_, c_ in c.most_common()]]
        out.append("")
    print("\n".join(out))
main()
